package com.example.xclmitigation;

import android.app.PendingIntent;
import android.app.assist.AssistStructure;
import android.content.Intent;
import android.content.IntentSender;
import android.os.CancellationSignal;
import android.service.autofill.AutofillService;
import android.service.autofill.Dataset;
import android.service.autofill.FillCallback;
import android.service.autofill.FillContext;
import android.service.autofill.FillRequest;
import android.service.autofill.FillResponse;
import android.service.autofill.SaveCallback;
import android.service.autofill.SaveRequest;
import android.util.Log;
import android.view.autofill.AutofillId;
import android.view.autofill.AutofillValue;
import android.widget.RemoteViews;

import java.util.ArrayList;
import java.util.List;

public class SecureAutofillService extends AutofillService {

    final static String TAG = "SecureAutofillService";


    @Override
    public void onFillRequest(FillRequest request, CancellationSignal cancellationSignal,
                              FillCallback callback) {

        // 1. Parse the structure just to find Input Fields (for later filling)
        // In a real sevice, you'd find the focussed field. If it is a virtual structure (browser)
        // You'd find the webDomain associated with the form fields
        // For this PoC, we just simply fill the first two idìs found.

        List<AutofillId> foundIds = parseStructure(request.getFillContexts().get(request.getFillContexts().size() - 1));

        if (foundIds.isEmpty() || foundIds.size() < 2) {
            callback.onSuccess(null);
            return;
        }

        AutofillId usernameId = foundIds.get(0);
        AutofillId passwordId = foundIds.get(1);

        // For the sake of simplicity in this PoC we hardcode a.com as a webDomain
        // in a real service, you would find the proper domain from the structure
        String webDomain = "a.com";
        // Get the package name from the request:
        String packageName = request.getFillContexts().get(request.getFillContexts().size() - 1).getStructure().getActivityComponent().getPackageName();


        // 2. check for the Digital Asset Link as described in:
        // https://developer.android.com/reference/android/service/autofill/AutofillService#web-security
        // for the sake of the PoC, we just assume that the check fails
        boolean isDigitalAssetLink = false;

        // if digital asset link check passes, simply use the normal interaction code
        // https://developer.android.com/identity/autofill/autofill-services
        if (isDigitalAssetLink) {
            callback.onSuccess(null);
        } else {
            // 3. Prepare the "Gatekeeper" Intent
            // We pass the package name of the requesting app
            // We also pass the ids of the views we want to fill and the associated webDomain
            Intent intent = new Intent(this, WarningActivity.class);

            intent.putExtra("usernameId", usernameId);
            intent.putExtra("passwordId", passwordId);
            intent.putExtra("domain", webDomain);
            intent.putExtra("packageName", packageName);


            IntentSender sender = PendingIntent.getActivity(this, 1001, intent,
                    PendingIntent.FLAG_CANCEL_CURRENT | PendingIntent.FLAG_IMMUTABLE).getIntentSender();

            // 4. Create the "Constant Size" Generic Dataset
            RemoteViews presentation = new RemoteViews(getPackageName(), android.R.layout.simple_list_item_1);
            presentation.setTextViewText(android.R.id.text1, "Tap to Verify (Security Check)");

            Dataset.Builder lockedDataset = new Dataset.Builder(presentation);
            lockedDataset.setAuthentication(sender);

            // We must attach this dataset to the found IDs.
            // The value "locked" is a placeholder;
            for (AutofillId id : foundIds) {
                lockedDataset.setValue(id, AutofillValue.forText("locked"));
            }

            // 4. Return the response
            FillResponse response = new FillResponse.Builder()
                    .addDataset(lockedDataset.build())
                    .build();

            callback.onSuccess(response);
        }

    }

    @Override
    public void onSaveRequest(SaveRequest request, SaveCallback callback) {
        // Not needed for this PoC
        callback.onSuccess();
    }

    // Helper to find input fields in the view hierarchy
    private List<AutofillId> parseStructure(FillContext context) {
        List<AutofillId> ids = new ArrayList<>();
        AssistStructure structure = context.getStructure();
        int nodes = structure.getWindowNodeCount();
        for (int i = 0; i < nodes; i++) {
            traverseNode(structure.getWindowNodeAt(i).getRootViewNode(), ids);
        }
        return ids;
    }

    private void traverseNode(AssistStructure.ViewNode node, List<AutofillId> ids) {
        if (node == null) return;

        // 1. Get the class name safely
        String className = node.getClassName();

        // 2. CHECK IF NULL before calling .contains()
        if (className != null && className.contains("EditText")) {
            if (node.getAutofillId() != null) {
                ids.add(node.getAutofillId());
                Log.d(TAG, "Found EditText with ID: " + node.getAutofillId());
            }
        }

        // 3. Recursively check children
        for (int i = 0; i < node.getChildCount(); i++) {
            traverseNode(node.getChildAt(i), ids);
        }
    }
}