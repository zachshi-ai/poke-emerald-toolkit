package com.stepx.pokeemerald;

import android.content.Context;

public class AppCtx {
    private static Context ctx;

    static void set(Context c) {
        if (c != null) ctx = c.getApplicationContext();
    }

    static Context get() {
        return ctx;
    }
}
