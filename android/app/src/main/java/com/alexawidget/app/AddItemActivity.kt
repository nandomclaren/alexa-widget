package com.alexawidget.app

import android.appwidget.AppWidgetManager
import android.content.ComponentName
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.widget.Button
import android.widget.EditText
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity

/** Diálogo leve aberto a partir do botão "+" do widget, sem abrir o app inteiro. */
class AddItemActivity : AppCompatActivity() {

    private lateinit var api: ApiClient
    private var appWidgetId: Int = AppWidgetManager.INVALID_APPWIDGET_ID

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_add_item)

        api = ApiClient(this)
        appWidgetId = intent.getIntExtra(AppWidgetManager.EXTRA_APPWIDGET_ID, AppWidgetManager.INVALID_APPWIDGET_ID)

        val input = findViewById<EditText>(R.id.add_item_input)
        input.requestFocus()

        findViewById<Button>(R.id.add_item_confirm).setOnClickListener {
            val text = input.text.toString().trim()
            if (text.isEmpty()) {
                finish()
            } else {
                submit(text)
            }
        }
        findViewById<Button>(R.id.add_item_cancel).setOnClickListener { finish() }
    }

    private fun submit(text: String) {
        val handler = Handler(Looper.getMainLooper())
        Thread {
            try {
                api.addItemBlocking(text)
                handler.post {
                    refreshWidgets()
                    finish()
                }
            } catch (e: Exception) {
                handler.post {
                    Toast.makeText(this, e.message ?: getString(R.string.unknown_error), Toast.LENGTH_LONG).show()
                }
            }
        }.start()
    }

    private fun refreshWidgets() {
        val manager = AppWidgetManager.getInstance(this)
        val ids = if (appWidgetId != AppWidgetManager.INVALID_APPWIDGET_ID) {
            intArrayOf(appWidgetId)
        } else {
            manager.getAppWidgetIds(ComponentName(this, ShoppingListWidgetProvider::class.java))
        }
        manager.notifyAppWidgetViewDataChanged(ids, R.id.widget_list)
    }
}
