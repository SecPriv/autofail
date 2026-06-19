package com.example.xclmitigation;

import android.app.Activity;
import android.content.Intent;
import android.os.Bundle;
import android.service.autofill.Dataset;
import android.service.autofill.FillResponse;
import android.view.autofill.AutofillId;
import android.view.autofill.AutofillManager;
import android.view.autofill.AutofillValue;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.RemoteViews;
import android.widget.TextView;

public class WarningActivity extends Activity {

    String webDomain = null;
    String packageName = null;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        String webDomain = getIntent().getStringExtra("domain");
        String packageName = getIntent().getStringExtra("packageName");


        // 1. Minimalistic UI: Warning Text + Confirm Button
        LinearLayout layout = new LinearLayout(this);
        layout.setOrientation(LinearLayout.VERTICAL);
        layout.setPadding(50, 50, 50, 50);

        TextView warning = new TextView(this);
        warning.setText("SECURITY WARNING\n\nThe website " + webDomain + " seems not to be associated with "+ packageName + ". This could be a phishing attempt.\n\nDo you want to proceed?");
        layout.addView(warning);

        Button btnConfirm = new Button(this);
        btnConfirm.setText("Yes, I trust this site");
        layout.addView(btnConfirm);

        setContentView(layout);

        // 2. Handle User Confirmation
        btnConfirm.setOnClickListener(v -> unlockCredentials());
    }

    private void unlockCredentials() {
        // Retrieve the AutofillIds and webDomain we passed from the Service
        AutofillId passwordId = getIntent().getParcelableExtra("passwordId", AutofillId.class);
        AutofillId usernameId = getIntent().getParcelableExtra("usernameId", AutofillId.class);



        // 3. Construct the "Real" Response
        // Now that the user has acknowledged the risk, we create the response
        // with the actual credentials.
        FillResponse.Builder responseBuilder = new FillResponse.Builder();

        // use pwm heuristic to find the credentials for the webDomain / pckgname . For the sake of the PoC
        // we just hardcode them
        AutofillValue username = AutofillValue.forText("admin");
        AutofillValue password = AutofillValue.forText("superSecretPass123");

        // Create a presentation for the actual credentials
        RemoteViews credentialPresentation = new RemoteViews(getPackageName(), android.R.layout.simple_list_item_1);
        credentialPresentation.setTextViewText(android.R.id.text1, "admin / *******");

        // Create the dataset that actually fills the fields
        Dataset.Builder datasetBuilder = new Dataset.Builder(credentialPresentation);

        datasetBuilder.setValue(usernameId, username);
        datasetBuilder.setValue(passwordId, password);
        responseBuilder.addDataset(datasetBuilder.build());

        // 4. Return the result to AutofillManager
        Intent replyIntent = new Intent();
        replyIntent.putExtra(AutofillManager.EXTRA_AUTHENTICATION_RESULT, responseBuilder.build());

        setResult(RESULT_OK, replyIntent);
        finish();
    }
}