
import Java from "frida-java-bridge";

'use strict';


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

    function handleAutofill(sessionId, ids, values) {

        var dump = {
            type: "AutofillAction",
            sequenceNumber: globalSequenceNumber,
            timestamp: Date.now(),
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
                    
                    // Values might be null in some partial updates
                    var valObj = (i < valuesList.size()) ? valuesList.get(i) : null;
                    var valStr = "null";
                    
                    if (valObj) {
                        var afVal = Java.cast(valObj, AutofillValue);
                        valStr = getValStr(afVal);
                    }

                    dump.data.push({
                        id: afId.toString(),
                        value: valStr
                    });
                }
            }
        } catch (e) {
            dump.error = e.message;
            console.log("[-] Parsing Error: " + e.message);
        }

        // --- WRITE TO FILE (Orchestrator compatible) ---
        // Note: For your Python Orchestrator to read this instantly, 
        // you usually use send(JSON.stringify(dump)) instead of File IO.
        // I kept File IO because that's what you pasted, but send() is preferred!
        try {
            // Check if we are sending to python (uncomment to enable)
            send(JSON.stringify(dump)); 

            // File Fallback
            var context = ActivityThread.currentApplication().getApplicationContext();
            var dir = context.getFilesDir();
            var fileName = "fill_" + globalSequenceNumber + ".json";
            var file = File.$new(dir, fileName);
            
            var jsonString = JSON.stringify(dump, null, 2);
            var fos = FileOutputStream.$new(file);
            fos.write(StringClass.$new(jsonString).getBytes());
            fos.close();

            globalSequenceNumber++;

        } catch (ioErr) {
            console.log("[-] Write Error: " + ioErr.message);
        }
    }

    // --- ROBUST HOOKING (Catches ALL Overloads) ---
    var autofillOverloads = AutofillManager.autofill.overloads;
    
    autofillOverloads.forEach(function(overload) {
        overload.implementation = function() {
            // Arguments vary in length (3 or 4 args)
            // Signature 1: (int, List, List)
            // Signature 2: (int, List, List, boolean)
            
            var sessionId = arguments[0];
            var ids = arguments[1];
            var values = arguments[2];
            // arguments[3] would be 'boolean hideHighlight' if present

            // Process the data
            handleAutofill(sessionId, ids, values);

            // Call original
            return this.autofill.apply(this, arguments);
        };
    });

});