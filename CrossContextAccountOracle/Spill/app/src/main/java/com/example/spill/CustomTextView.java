package com.example.spill;

import android.content.Context;
import android.graphics.Color;
import android.graphics.Rect;
import android.util.AttributeSet;
import android.util.DisplayMetrics;
import android.util.Log;
import android.util.TypedValue;
import android.view.View;
import android.view.ViewStructure;
import android.view.autofill.AutofillManager;
import android.view.autofill.AutofillValue;

import androidx.annotation.NonNull;
import androidx.annotation.Nullable;

public class CustomTextView extends androidx.appcompat.widget.AppCompatEditText {

    private final static String TAG = "CustomTextView";

    public CustomTextView(@NonNull Context context) {
        super(context);
    }

    public CustomTextView(@NonNull Context context, @Nullable AttributeSet attrs) {
        super(context, attrs);
    }

    public CustomTextView(@NonNull Context context, @Nullable AttributeSet attrs, int defStyleAttr) {
        super(context, attrs, defStyleAttr);
    }

    /* The code in this function recreates the strucutre sent by a browser (e.g Firefox)
       Otherwise the password manager could not send the credentials back
     */
    @Override
    public void onProvideAutofillVirtualStructure(ViewStructure structure, int flags) {
        Log.d(TAG, "call to onProvideAutofillVirtualStructure");
        super.onProvideAutofillVirtualStructure(structure, flags);

        if(MainActivity.index < MainActivity.domains.size()) {
            String currDomain = MainActivity.domains.get(MainActivity.index);

            structure.setWebDomain(currDomain);
            structure.setClassName("android.view.ViewGroup");
            structure.setAutofillType(View.AUTOFILL_TYPE_NONE);
            // Text-related properties
            structure.setTextStyle(0, 0, 1, 1); // size=0, style=0, textColor=1, backgroundColor=1
            // View properties
            structure.setVisibility(View.VISIBLE);
            structure.setDimens(0, 0, 0, 0, 414, 781);
            structure.setElevation(0);
            structure.setAlpha(1f);
            // State flags
            structure.setEnabled(true);
            structure.setClickable(false);
            structure.setLongClickable(false);
            structure.setFocusable(false);
            structure.setFocused(false);
            structure.setContextClickable(false);
            structure.setCheckable(false);
            structure.setChecked(false);
            structure.setSelected(false);
            // Autofill importance
            structure.setImportantForAutofill(View.IMPORTANT_FOR_AUTOFILL_YES);
            structure.setAutofillId(structure.getAutofillId(), 1111);
            structure.setId(2, null, null, null);
            structure.setChildCount(2);


            // email
            ViewStructure passwordChild = structure.newChild(0);
            // Basic view info.setClassName("android.widget.EditText");
            passwordChild.setId(2, null, null, null);
            passwordChild.setAutofillType(View.AUTOFILL_TYPE_TEXT);
            passwordChild.setWebDomain(currDomain);
            // Text attributes
            passwordChild.setTextStyle(0, 1, 1, 1);  // size=0, style=0, textColor=1, backgroundColor=1
            // Visibility and layout
            passwordChild.setVisibility(View.VISIBLE);
            passwordChild.setDimens(0, 0, 0, 0, 313, 20);
            passwordChild.setElevation(0);
            passwordChild.setAlpha(1f);
            // State flags
            passwordChild.setEnabled(true);
            passwordChild.setClickable(false);
            passwordChild.setLongClickable(false);
            passwordChild.setFocusable(true);
            passwordChild.setFocused(false);
            passwordChild.setContextClickable(false);
            passwordChild.setCheckable(false);
            passwordChild.setChecked(false);
            passwordChild.setSelected(false);
            // Input type (e.g. textEmailAddress | textVisiblePassword)
            passwordChild.setInputType(225);
            // Autofill importance
            passwordChild.setImportantForAutofill(View.IMPORTANT_FOR_AUTOFILL_YES);
            passwordChild.setAutofillHints(new String[]{"password"});
            ViewStructure.HtmlInfo.Builder hib = passwordChild.newHtmlInfoBuilder("input");
            hib.addAttribute("autocorrect", "off");
            hib.addAttribute("autocomplete", "on");
            hib.addAttribute("name", "pass");
            hib.addAttribute("style", "background: transparent; color: rgb(10, 19, 23); font-family: \\\"Optimistic 95\\\"; font-size: 15.2px; line-height: 1.3; caret-color: rgb(10, 19, 23);");
            hib.addAttribute("data-bloks-name", "bk.components.TextInput");
            hib.addAttribute("id", "m_login_password");
            hib.addAttribute("dir", "auto");
            hib.addAttribute("type", "password");
            hib.addAttribute("class", "wbloks_1 wbloks_66");
            hib.addAttribute("autocapitalize", "none");
            hib.addAttribute("aria-label", "Password");
            passwordChild.setHtmlInfo(hib.build());
            passwordChild.setAutofillId(this.getAutofillId(), 2222);


            ViewStructure emailChild = structure.newChild(1);
            emailChild.setAutofillId(this.getAutofillId(), 3333);
            emailChild.setId(2, null, null, null);
            emailChild.setWebDomain(currDomain);
            emailChild.setClassName("android.widget.EditText");
            emailChild.setAutofillType(View.AUTOFILL_TYPE_TEXT);
            emailChild.setTextStyle(0, 1, 1, 1);  // textSize=0, textStyle=0, textColor=1, backgroundColor=1
            // Layout and rendering properties
            emailChild.setVisibility(View.VISIBLE);
            emailChild.setDimens(0, 0, 0, 0, 313, 20);
            emailChild.setElevation(0);
            emailChild.setAlpha(1f);


            // State flags
            emailChild.setEnabled(true);
            emailChild.setClickable(false);
            emailChild.setLongClickable(false);
            emailChild.setFocusable(true);
            emailChild.setFocused(false);
            emailChild.setContextClickable(false);
            emailChild.setCheckable(false);
            emailChild.setChecked(false);
            emailChild.setSelected(false);
            emailChild.setAutofillHints(new String[]{"emailAddress"});
            hib = emailChild.newHtmlInfoBuilder("input");
            hib.addAttribute("autocorrect", "off");
            hib.addAttribute("autocomplete", "on");
            hib.addAttribute("name", "email");
            hib.addAttribute("style", "background: transparent; color: rgb(10, 19, 23); font-family: \\\"Optimistic 95\\\"; font-size: 15.2px; line-height: 1.3; caret-color: rgb(10, 19, 23);");
            hib.addAttribute("data-bloks-name", "bk.components.TextInput");
            hib.addAttribute("dir", "auto");
            hib.addAttribute("id", "m_login_email");
            hib.addAttribute("type", "email");
            hib.addAttribute("class", "wbloks_1 wbloks_66");
            hib.addAttribute("autocapitalize", "none");
            hib.addAttribute("aria-label", "Mobile number or email");
            emailChild.setHtmlInfo(hib.build());

            // Input type (33 usually = TYPE_TEXT_VARIATION_EMAIL_ADDRESS | TYPE_CLASS_TEXT)
            emailChild.setInputType(33);

            // Autofill importance
            emailChild.setImportantForAutofill(View.IMPORTANT_FOR_AUTOFILL_YES);
        }
    }

}