package com.alexawidget.app

import android.content.Context
import android.net.Uri
import org.json.JSONArray
import org.json.JSONObject
import java.io.IOException
import java.io.OutputStream
import java.net.HttpURLConnection
import java.net.URL

/**
 * Cliente HTTP para a API do Alexa Shopping List Bridge.
 *
 * Todos os métodos aqui são bloqueantes de propósito: quem chama (Activity,
 * RemoteViewsFactory, BroadcastReceiver) é responsável por rodar isso fora da
 * thread principal. Isso evita depender de bibliotecas de coroutines/HTTP
 * externas — só usa o que já vem no Android.
 */
class ApiClient(context: Context) {

    private val settings = SettingsStore(context.applicationContext)

    data class ShoppingItem(
        val id: String,
        val text: String,
        val completed: Boolean,
        val createdDate: String?,
    )

    data class HealthResult(
        val authenticated: Boolean,
        val state: String,
        val message: String?,
    )

    class ApiException(message: String) : IOException(message)

    private fun baseUrl(): String {
        val url = settings.serverUrl.trim().trimEnd('/')
        if (url.isEmpty()) {
            throw ApiException("Configure a URL do servidor nas configurações do app")
        }
        return url
    }

    private fun openConnection(path: String, method: String): HttpURLConnection {
        val connection = URL(baseUrl() + path).openConnection() as HttpURLConnection
        connection.requestMethod = method
        connection.connectTimeout = 10_000
        connection.readTimeout = 15_000
        val token = settings.token.trim()
        if (token.isNotEmpty()) {
            connection.setRequestProperty("Authorization", "Bearer $token")
        }
        connection.setRequestProperty("Accept", "application/json")
        return connection
    }

    private fun writeJsonBody(connection: HttpURLConnection, json: JSONObject) {
        connection.doOutput = true
        connection.setRequestProperty("Content-Type", "application/json")
        val bytes = json.toString().toByteArray(Charsets.UTF_8)
        connection.setFixedLengthStreamingMode(bytes.size)
        val out: OutputStream = connection.outputStream
        out.use { it.write(bytes) }
    }

    private fun readBody(connection: HttpURLConnection): String {
        val stream = if (connection.responseCode in 200..299) {
            connection.inputStream
        } else {
            connection.errorStream
        }
        return stream?.bufferedReader(Charsets.UTF_8)?.use { it.readText() } ?: ""
    }

    private fun checkResponse(connection: HttpURLConnection, body: String) {
        if (connection.responseCode !in 200..299) {
            val message = try {
                JSONObject(body).optString("message", body)
            } catch (e: Exception) {
                body.ifBlank { "Erro HTTP ${connection.responseCode}" }
            }
            throw ApiException(message)
        }
    }

    private fun parseItem(json: JSONObject): ShoppingItem = ShoppingItem(
        id = json.optString("id"),
        text = json.optString("text"),
        completed = json.optBoolean("completed", false),
        createdDate = if (json.isNull("created_date")) null else json.opt("created_date")?.toString(),
    )

    fun healthBlocking(): HealthResult {
        val connection = openConnection("/health", "GET")
        try {
            val body = readBody(connection)
            checkResponse(connection, body)
            val json = JSONObject(body)
            val amazon = json.optJSONObject("amazon_session") ?: JSONObject()
            return HealthResult(
                authenticated = amazon.optBoolean("authenticated", false),
                state = amazon.optString("state", "desconhecido"),
                message = if (amazon.isNull("message")) null else amazon.optString("message", null),
            )
        } finally {
            connection.disconnect()
        }
    }

    fun listItemsBlocking(): List<ShoppingItem> {
        val connection = openConnection("/api/lists/shopping", "GET")
        try {
            val body = readBody(connection)
            checkResponse(connection, body)
            val array = JSONArray(body)
            return (0 until array.length()).map { i -> parseItem(array.getJSONObject(i)) }
        } finally {
            connection.disconnect()
        }
    }

    fun addItemBlocking(text: String): ShoppingItem {
        val connection = openConnection("/api/lists/shopping", "POST")
        try {
            writeJsonBody(connection, JSONObject().put("text", text))
            val body = readBody(connection)
            checkResponse(connection, body)
            return parseItem(JSONObject(body))
        } finally {
            connection.disconnect()
        }
    }

    fun completeItemBlocking(id: String): ShoppingItem {
        val connection = openConnection("/api/lists/shopping/${Uri.encode(id)}/complete", "POST")
        try {
            connection.doOutput = true
            connection.setFixedLengthStreamingMode(0)
            connection.outputStream.use { /* corpo vazio */ }
            val body = readBody(connection)
            checkResponse(connection, body)
            return parseItem(JSONObject(body))
        } finally {
            connection.disconnect()
        }
    }

    fun deleteItemBlocking(id: String) {
        val connection = openConnection("/api/lists/shopping/${Uri.encode(id)}", "DELETE")
        try {
            val body = readBody(connection)
            checkResponse(connection, body)
        } finally {
            connection.disconnect()
        }
    }
}
