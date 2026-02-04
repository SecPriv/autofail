'use strict';

send("!!! SCRIPT INJECTED. INITIALIZING... !!!");

var retryCount = 0;

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
                ).implementation = function(req, sig, cb) {
                    var output = "\n======================================\n";
                    output += "[+] 🔓 BITWARDEN/1PASS REQUEST!\n";
                    output += "    Service: " + className + "\n";
                    output += "    Req ID:  " + req.getId() + "\n";
                    
                    try {
                        var context = req.getFillContexts().get(0);
                        output += "    Context: " + context.toString().substring(0, 100) + "...\n";
                    } catch(e) {}

                    send(output);
                    this.onFillRequest(req, sig, cb);
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