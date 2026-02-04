import Java from "frida-java-bridge";

'use strict';

send("!!! SCRIPT INJECTED. INITIALIZING... !!!");

var retryCount = 0;

var ListClz = Java.use("java.util.List");
var PairClz = Java.use("android.util.Pair");
var FillContextClz = Java.use("android.service.autofill.FillContext");

function parseHtmlInfo(htmlInfo) {
    if (!htmlInfo) return null;
    
    var info = {};
    info.tag = htmlInfo.getTag() ? htmlInfo.getTag() : "unknown";
    
    // HtmlInfo attributes are a List<Pair<String, String>>
    var rawAttrList = htmlInfo.getAttributes();
    if (rawAttrList) {
        info.attributes = {};
        var attrList = Java.cast(rawAttrList, ListClz);
        var size = attrList.size();
        
        for (var i = 0; i < size; i++) {
            // Each item is a Pair
            var pairObj = attrList.get(i);
            var pair = Java.cast(pairObj, PairClz);
            
            // .first and .second are public fields in Pair
            var key = pair.first.value ? pair.first.value.toString() : "null";
            var val = pair.second.value ? pair.second.value.toString() : "null";
            
            info.attributes[key] = val;
        }
    }
    return info;
}

// --- HELPER: Recursive Node Processor ---
function processViewNode(viewNode) {
    if (viewNode === null) return null;

    var nodeData = {};

    // 1. Basic Identifiers
    nodeData.className = viewNode.getClassName();
    
    var idEntry = viewNode.getIdEntry();
    if (idEntry !== null) nodeData.resourceId = idEntry;

    // 2. Autofill ID (Important for mapping requests)
    var afId = viewNode.getAutofillId();
    if (afId !== null) nodeData.autofillId = afId.toString();

    // 3. Focus & Flags
    nodeData.isFocused = viewNode.isFocused();
    if (nodeData.isFocused) {
        // Mark this node explicitly if you want to find it quickly in the JSON
        nodeData._NOTE_ = "THIS NODE IS FOCUSED"; 
    }

    // 4. Content (Text/Hints)
    var text = viewNode.getText();
    if (text !== null) nodeData.text = text.toString();

    var hint = viewNode.getHint();
    if (hint !== null) nodeData.hint = hint.toString();

    // 5. Autofill Hints (String Array)
    var afHints = viewNode.getAutofillHints(); // Returns String[]
    if (afHints !== null) {
        nodeData.autofillHints = [];
        // Javascript loop over Java Array works naturally in Frida
        for(var i = 0; i < afHints.length; i++) {
            nodeData.autofillHints.push(afHints[i]);
        }
    }

    // 6. Web Domain (for Browser/WebView)
    var domain = viewNode.getWebDomain();
    if (domain !== null) nodeData.webDomain = domain;
    
    // 7. Web Scheme (for Browser/WebView)
    var scheme = viewNode.getWebScheme();
    if (domain !== null) nodeData.scheme = scheme;

    // 8. HTML Info (Tag names, HTML attributes)
    var htmlInfo = viewNode.getHtmlInfo();
    if (htmlInfo !== null) {
        nodeData.htmlInfo = parseHtmlInfo(htmlInfo);
    }

    // --- Recursion for Children ---
    var childCount = viewNode.getChildCount();
    if (childCount > 0) {
        nodeData.children = [];
        for (var j = 0; j < childCount; j++) {
            var child = viewNode.getChildAt(j);
            nodeData.children.push(processViewNode(child));
        }
    }

    return nodeData;
}

// --- MAIN EXTRACTION LOGIC ---
function extractFillRequestData(request) {
    var dump = {};

    try {
        dump.requestId = request.getId();
        dump.flags = request.getFlags();
        
        var bundle = request.getClientState();
        dump.clientState = (bundle !== null) ? bundle.toString() : "null";

        dump.contexts = [];
        
        // Cast to List to safely iterate
        var rawList = request.getFillContexts();
        var contextsList = Java.cast(rawList, ListClz); 
        var size = contextsList.size();
        
        for (var i = 0; i < size; i++) {
            var rawCtx = contextsList.get(i);
            var ctx = Java.cast(rawCtx, FillContextClz);
            
            var ctxDump = {};
            ctxDump.requestId = ctx.getRequestId();
            
            // Parse the UI Tree
            var structure = ctx.getStructure(); 
            ctxDump.structure = parseAssistStructure(structure);
            
            dump.contexts.push(ctxDump);
        }

    } catch (e) {
        dump.error = "Error parsing request: " + e.message;
    }

    return dump;
}

function parseAssistStructure(structure) {
    var windowsDump = [];
    if (structure === null) return "null";

    var nodeCount = structure.getWindowNodeCount();
    for (var i = 0; i < nodeCount; i++) {
        var windowNode = structure.getWindowNodeAt(i);
        var rootNode = windowNode.getRootViewNode();
        
        windowsDump.push({
            title: windowNode.getTitle() ? windowNode.getTitle().toString() : "",
            root: processViewNode(rootNode)
        });
    }
    return windowsDump;
}


// We define the main logic as a function so we can call it later
function runHookingLogic() {
    send("[*] Java detected! Attaching to main thread...");

    Java.perform(function() {
        var AutofillService = Java.use('android.service.autofill.AutofillService');
        var Service = Java.use("android.app.Service");

        // Helper: Install hooks for a specific class
        function hookClass(className) {
            // Filter: Ignore system classes, focus on the App
            if (className.startsWith("android.") || className.startsWith("java.") || className.startsWith("com.android.")) return;

            try {
                var Clazz = Java.use(className);
                
                // Verify inheritance
                if (!AutofillService.class.isAssignableFrom(Clazz.class)) return;

                // Hook onFillRequest
                Clazz.onFillRequest.overload(
                    'android.service.autofill.FillRequest', 
                    'android.os.CancellationSignal', 
                    'android.service.autofill.FillCallback'
                ).implementation = function(request, signal, callback) {
                    
                    // 1. Generate JSON Object
                    var jsObject = extractFillRequestData(request);
                    var jsonString = JSON.stringify(jsObject, null, 2);
        
                    send(jsonString);
                    this.onFillRequest(request, signal, callback);
                };
                
                send("[+] Hooked Service: " + className);
            } catch(e) {
                // ignore errors
            }
        }

        // 1. Scan Heap (For services already alive)
        Java.choose("android.service.autofill.AutofillService", {
            onMatch: function(inst) {
                try { hookClass(inst.getClass().getName()); } catch(e) {}
            },
            onComplete: function() {}
        });

        // 2. Hook Creation (For new services)
        Service.onCreate.implementation = function() {
            var currentClass = this.getClass();
            if (AutofillService.class.isAssignableFrom(currentClass)) {
                send("[+] New AutofillService started: " + currentClass.getName());
                hookClass(currentClass.getName());
            }
            this.onCreate();
        };
    });
}

// --- THE ROBUST LOADER ---
// This prevents "ReferenceError: Java is not defined"
function attemptLoad() {
    if (typeof Java === 'undefined') {
        retryCount++;
        // Don't spam logs, only print every 10 retries (1 second)
        if (retryCount % 10 === 0) {
             send("[*] Waiting for Java bridge... (Attempt " + retryCount + ")");
        }
        // Try again in 100ms
        setTimeout(attemptLoad, 100);
    } else {
        // Java is ready! Run the code.
        runHookingLogic();
    }
}

// Start the loading process
attemptLoad();