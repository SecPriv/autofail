'use strict';

console.log("Waiting for Java..");

var hookApplied = false;
var globalSeq = 0;

Java.perform(function() {
    var Service = Java.use("android.app.Service");
    var AutofillService = Java.use('android.service.autofill.AutofillService');
    
    // File IO classes
    var File = Java.use('java.io.File');
    var FileOutputStream = Java.use('java.io.FileOutputStream');
    var StringClass = Java.use('java.lang.String');

    // Utility classes for Parsing
    var ListClz = Java.use("java.util.List");
    var PairClz = Java.use("android.util.Pair");
    var FillContextClz = Java.use("android.service.autofill.FillContext");

    // --- HELPER: HTML Info Parser (for WebViews) ---
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
            console.log("[-] Parsing Error: " + e.stack);
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

    // --- HOOK IMPLEMENTATION ---
    Service.onCreate.implementation = function() {
        var currentClass = this.getClass();
        console.log("\n[+] Service#onCreate called");

        if (AutofillService.class.isAssignableFrom(currentClass)) {
            console.log("\n[+] Autofill Service Found: " + currentClass.getName());
            
            try {
                var TargetService = Java.use(currentClass.getName());

                TargetService.onFillRequest.overload(
                    'android.service.autofill.FillRequest', 
                    'android.os.CancellationSignal', 
                    'android.service.autofill.FillCallback'
                ).implementation = function(request, signal, callback) {
                    
                    console.log("[+] HOOK HIT: onFillRequest");
                    
                    // 1. Generate JSON Object
                    var jsObject = extractFillRequestData(request);
                    var jsonString = JSON.stringify(jsObject, null, 2);

                    // 2. Write to File
                    try {
                        var dir = this.getFilesDir();
                        var fileName = "req_" + globalSeq + ".json";
                        var file = File.$new(dir, fileName);
                        
                        var fos = FileOutputStream.$new(file);
                        fos.write(StringClass.$new(jsonString).getBytes());
                        fos.close();

                        console.log("[+] JSON Saved: " + file.getAbsolutePath());

                    } catch (err) {
                        console.log("[-] File Write Failed: " + err.message);
                    }

                    // 3. Call Original
                    this.onFillRequest(request, signal, callback);
                };

                // (Optional) Hook callbacks to see results
                var callBackClass = Java.use("android.service.autofill.FillCallback");

                callBackClass.onSuccess.overload('android.service.autofill.FillResponse').implementation = function(response) {
                    console.log("[+] HOOK HIT: onSuccess");
                    this.onSuccess(response);
                };

                callBackClass.onFailure.overload('java.lang.CharSequence').implementation = function(message) {
                    console.log("[+] HOOK HIT: onFailure");
                    this.onFailure(message);
                };

                console.log("[+] Hooks attached!");
                hookApplied = true;

            } catch (e) {
                console.log("[-] Error hooking: " + e.message);
            }
        }
        this.onCreate();
    };
});

console.log("[*] Waiting for Service...");