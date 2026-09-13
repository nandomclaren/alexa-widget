package com.alexawidget.app

import android.appwidget.AppWidgetManager
import android.content.ComponentName
import android.content.Intent
import android.net.Uri
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.widget.Button
import android.widget.EditText
import android.widget.ListView
import android.widget.TextView
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import com.google.android.material.dialog.MaterialAlertDialogBuilder
import com.google.android.material.tabs.TabLayout

class MainActivity : AppCompatActivity() {

    private lateinit var settings: SettingsStore
    private lateinit var api: ApiClient
    private lateinit var statusText: TextView
    private lateinit var itemsListView: ListView
    private lateinit var itemsAdapter: ShoppingListAdapter

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        settings = SettingsStore(this)
        api = ApiClient(this)

        setupTabs()

        val serverUrlInput = findViewById<EditText>(R.id.server_url_input)
        val tokenInput = findViewById<EditText>(R.id.token_input)
        serverUrlInput.setText(settings.serverUrl)
        tokenInput.setText(settings.token)

        statusText = findViewById(R.id.status_text)
        itemsListView = findViewById(R.id.items_list_view)
        itemsAdapter = ShoppingListAdapter(
            context = this,
            onToggle = { item ->
                runInBackground(
                    action = { api.setItemCompletedBlocking(item.id, !item.completed) },
                    onSuccess = { loadItems() },
                    onError = { showError(it) },
                )
            },
            onEdit = { item -> showRenameDialog(item) },
            onDelete = { item ->
                runInBackground(
                    action = { api.deleteItemBlocking(item.id) },
                    onSuccess = { loadItems() },
                    onError = { showError(it) },
                )
            },
        )
        itemsListView.adapter = itemsAdapter

        findViewById<Button>(R.id.save_settings_button).setOnClickListener {
            settings.serverUrl = serverUrlInput.text.toString().trim()
            settings.token = tokenInput.text.toString().trim()
            Toast.makeText(this, R.string.settings_saved, Toast.LENGTH_SHORT).show()
            updateAllWidgets()
        }

        findViewById<Button>(R.id.test_connection_button).setOnClickListener { testConnection() }

        findViewById<Button>(R.id.open_login_button).setOnClickListener {
            val url = settings.serverUrl.trim()
            if (url.isEmpty()) {
                Toast.makeText(this, R.string.configure_server_first, Toast.LENGTH_SHORT).show()
            } else {
                startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(url)))
            }
        }

        findViewById<Button>(R.id.add_item_button).setOnClickListener {
            val input = findViewById<EditText>(R.id.new_item_input)
            val text = input.text.toString().trim()
            if (text.isEmpty()) return@setOnClickListener
            input.setText("")
            runInBackground(
                action = { api.addItemBlocking(text) },
                onSuccess = { loadItems() },
                onError = { showError(it) },
            )
        }

        findViewById<Button>(R.id.refresh_list_button).setOnClickListener { loadItems() }

        loadItems()
    }

    private fun setupTabs() {
        val tabLayout = findViewById<TabLayout>(R.id.tab_layout)
        val listPage = findViewById<android.view.View>(R.id.list_page)
        val settingsPage = findViewById<android.view.View>(R.id.settings_page)

        tabLayout.addOnTabSelectedListener(object : TabLayout.OnTabSelectedListener {
            override fun onTabSelected(tab: TabLayout.Tab) {
                listPage.visibility = if (tab.position == 0) android.view.View.VISIBLE else android.view.View.GONE
                settingsPage.visibility = if (tab.position == 1) android.view.View.VISIBLE else android.view.View.GONE
            }

            override fun onTabUnselected(tab: TabLayout.Tab) {}
            override fun onTabReselected(tab: TabLayout.Tab) {}
        })
    }

    override fun onResume() {
        super.onResume()
        // Recarrega em caso de o usuário ter voltado do navegador após reautenticar.
        loadItems()
    }

    private fun testConnection() {
        statusText.text = getString(R.string.checking)
        runInBackground(
            action = { api.healthBlocking() },
            onSuccess = { result ->
                statusText.text = if (result.authenticated) {
                    getString(R.string.status_authenticated)
                } else {
                    getString(R.string.status_not_authenticated, result.state)
                }
            },
            onError = { showError(it) },
        )
    }

    private fun loadItems() {
        runInBackground(
            action = { api.listItemsBlocking() },
            onSuccess = { items -> itemsAdapter.submitList(items) },
            onError = { /* silencioso: pode ainda não estar autenticado/configurado */ },
        )
    }

    private fun showRenameDialog(item: ApiClient.ShoppingItem) {
        val density = resources.displayMetrics.density
        val padding = (20 * density).toInt()
        val input = EditText(this).apply {
            setText(item.text)
            setSelection(text.length)
        }
        val container = android.widget.FrameLayout(this).apply {
            setPadding(padding, padding / 2, padding, 0)
            addView(input)
        }
        MaterialAlertDialogBuilder(this)
            .setTitle(R.string.rename_item_title)
            .setView(container)
            .setPositiveButton(R.string.save) { _, _ ->
                val newText = input.text.toString().trim()
                if (newText.isNotEmpty() && newText != item.text) {
                    runInBackground(
                        action = { api.renameItemBlocking(item.id, newText) },
                        onSuccess = { loadItems() },
                        onError = { showError(it) },
                    )
                }
            }
            .setNegativeButton(R.string.cancel, null)
            .show()
    }

    private fun showError(e: Exception) {
        Toast.makeText(this, e.message ?: getString(R.string.unknown_error), Toast.LENGTH_LONG).show()
    }

    private fun updateAllWidgets() {
        val manager = AppWidgetManager.getInstance(this)
        val ids = manager.getAppWidgetIds(ComponentName(this, ShoppingListWidgetProvider::class.java))
        manager.notifyAppWidgetViewDataChanged(ids, R.id.widget_list)
    }

    private fun <T> runInBackground(action: () -> T, onSuccess: (T) -> Unit, onError: (Exception) -> Unit) {
        val handler = Handler(Looper.getMainLooper())
        Thread {
            try {
                val result = action()
                handler.post { onSuccess(result) }
            } catch (e: Exception) {
                handler.post { onError(e) }
            }
        }.start()
    }
}
