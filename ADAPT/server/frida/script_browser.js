'use strict';

console.log("[*] Waiting for Java...");

// --- GLOBAL STATE ---
var globalSequenceNumber = 0;

Java.perform(function() {
    var AutofillManager = Java.use("android.view.autofill.AutofillManager");
    var List = Java.use("java.util.List");
    var AutofillId = Java.use("android.view.autofill.AutofillId");
    var AutofillValue = Java.use("android.view.autofill.AutofillValue");
    
    var File = Java.use('java.io.File');
    var FileOutputStream = Java.use('java.io.FileOutputStream');
    var StringClass = Java.use('java.lang.String');
    var ActivityThread = Java.use('android.app.ActivityThread');

    function getValStr(val) {
        if (!val) return "null";
        try {
            if (val.isText()) return val.getTextValue().toString();
            if (val.isList()) return "ListIndex:" + val.getListValue();
            if (val.isToggle()) return "Toggle:" + val.getToggleValue();
            if (val.isDate()) return "Date:" + val.getDateValue();
        } catch (e) {}
        return "UnknownType";
    }

    try {
        var targetMethod = AutofillManager.autofill.overload(
            'int', 'java.util.List', 'java.util.List', 'boolean'
        );

        targetMethod.implementation = function(sessionId, ids, values, hideHighlight) {
            console.log("\n[+] HOOK HIT: AutofillManager.autofill (Seq: " + globalSequenceNumber + ")");

            var dump = {
                type: "AutofillAction",
                sequenceNumber: globalSequenceNumber,
                timestamp: Date.now(), // ADDED TIMESTAMP
                sessionId: sessionId,
                data: []
            };

            try {
                if (ids != null && values != null) {
                    var idsList = Java.cast(ids, List);
                    var valuesList = Java.cast(values, List);
                    var size = idsList.size();

                    for (var i = 0; i < size; i++) {
                        var idObj = idsList.get(i);
                        var afId = Java.cast(idObj, AutofillId);
                        var valObj = valuesList.get(i);
                        var afVal = Java.cast(valObj, AutofillValue);

                        dump.data.push({
                            id: afId.toString(),
                            value: getValStr(afVal)
                        });
                    }
                }
            } catch (e) {
                dump.error = e.message;
            }

            // --- WRITE TO FILE ---
            try {
                var context = ActivityThread.currentApplication().getApplicationContext();
                var dir = context.getFilesDir();
                
                // FILE NAME: fill_[SEQUENCE].json
                var fileName = "fill_" + globalSequenceNumber + ".json";
                var file = File.$new(dir, fileName);
                
                var jsonString = JSON.stringify(dump, null, 2);
                var fos = FileOutputStream.$new(file);
                fos.write(StringClass.$new(jsonString).getBytes());
                fos.close();

                console.log("[+] SAVED: " + file.getAbsolutePath());
                

            } catch (ioErr) {
                console.log("[-] File Write Error: " + ioErr.message);
            }

            this.autofill(sessionId, ids, values, hideHighlight);
        };
        console.log("[+] Hook attached!");
    } catch (err) {
        console.log("[-] Failed to hook: " + err.message);
    }
});