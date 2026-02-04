'use strict';

console.log("Waiting for Java..");



var hookApplied = false;

Java.perform(function() {
    var Service = Java.use("android.app.Service");
    var AutofillService = Java.use('android.service.autofill.AutofillService');

    // We hook the base 'onCreate' method of all Services
    Service.onCreate.implementation = function() {
        
        // 1. Get the class name of the service being created
        var currentClass= this.getClass();

        // 2. Check if it matches Bitwarden
        if (AutofillService.class.isAssignableFrom(currentClass)) {
            console.log("\n[+] Autofill Service Created: " + currentClass.getName);
            
            try {
                // 3. Now it is 100% safe to hook the method because 'this' exists
                var TargetService = Java.use(targetClass);

                TargetService.onFillRequest.overload(
                    'android.service.autofill.FillRequest', 
                    'android.os.CancellationSignal', 
                    'android.service.autofill.FillCallback'
                ).implementation = function(request, signal, callback) {
                    
                    console.log("[+] HOOK HIT: onFillRequest");
                    console.log("    Request ID: " + request.getId());
                    
                    // Call original
                    this.onFillRequest(request, signal, callback);
                };

                var callBackClass = Java.use("android.service.autofill.FillCallback");

                callBackClass.onSuccess.overload(
                    'android.service.autofill.FillResponse'
                ).implementation = function(response) {
                    console.log("[+] HOOK HIT: onSuccess");
                };

                callBackClass.onFailure.overload(
                    'java.lang.CharSequence'
                ).implementation = function(response) {
                    console.log("[+] HOOK HIT: onFailure");
                };


                console.log("[+] Hooks attached successfully!");
                hookApplied = true;

            } catch (e) {
                console.log("[-] Error hooking onFillRequest: " + e.message);
            }
        }

        // 4. IMPORTANT: Always call the original onCreate
        this.onCreate();
    };
});

console.log("[*] Waiting for Service.onCreate()...");