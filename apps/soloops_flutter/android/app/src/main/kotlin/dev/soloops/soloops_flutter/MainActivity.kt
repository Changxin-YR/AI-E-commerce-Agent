package dev.soloops.soloops_flutter

import android.app.Activity
import android.content.ClipData
import android.content.Intent
import android.net.Uri
import android.os.Build
import android.provider.OpenableColumns
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyInfo
import android.security.keystore.KeyProperties
import android.util.AtomicFile
import androidx.core.content.FileProvider
import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodCall
import io.flutter.plugin.common.MethodChannel
import java.io.ByteArrayOutputStream
import java.io.File
import java.security.KeyStore
import java.security.MessageDigest
import java.util.concurrent.Executors
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.SecretKeyFactory
import javax.crypto.spec.GCMParameterSpec

/** Debug-only M0 system capabilities. No production credentials or business rules. */
class MainActivity : FlutterActivity() {
    private val worker = Executors.newSingleThreadExecutor()
    private var picker: MethodChannel.Result? = null
    private var sharedUri: Uri? = null
    private val keyAlias = "soloops.m0.synthetic.v1"
    private val maxBytes = 2 * 1024 * 1024
    private val secureFile get() = File(noBackupFilesDir, "m0-secret.bin")
    private val cache get() = getSharedPreferences("m0-nonsensitive", MODE_PRIVATE)

    override fun configureFlutterEngine(engine: FlutterEngine) {
        super.configureFlutterEngine(engine)
        MethodChannel(engine.dartExecutor.binaryMessenger, "soloops/m0").setMethodCallHandler { call, result ->
            if (!BuildConfig.DEBUG) {
                result.error("DEBUG_ONLY", "M0 diagnostics are disabled", null)
            } else if (call.method == "pick") {
                if (picker != null) result.error("BUSY", "Picker already active", null)
                else {
                    picker = result
                    try {
                        startActivityForResult(Intent(Intent.ACTION_OPEN_DOCUMENT).apply {
                            addCategory(Intent.CATEGORY_OPENABLE)
                            type = "*/*"
                            addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
                        }, 4101)
                    } catch (e: Exception) {
                        picker = null
                        result.error("PICKER_UNAVAILABLE", e.javaClass.simpleName, null)
                    }
                }
            } else if (call.method == "share") {
                try {
                    val bytes = call.argument<ByteArray>("bytes") ?: error("Missing bytes")
                    require(bytes.size <= maxBytes)
                    clearShare()
                    val file = File(cacheDir, "m0-share/synthetic.txt")
                    file.parentFile!!.mkdirs()
                    file.writeBytes(bytes)
                    val uri = FileProvider.getUriForFile(this, "$packageName.m0files", file)
                    sharedUri = uri
                    val send = Intent(Intent.ACTION_SEND).apply {
                        type = "text/plain"
                        putExtra(Intent.EXTRA_STREAM, uri)
                        clipData = ClipData.newRawUri("M0 synthetic", uri)
                        addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
                    }
                    startActivity(Intent.createChooser(send, "M0 合成文件"))
                    // Neither this return nor an activity result proves channel delivery.
                    result.success("panel_opened")
                } catch (e: Exception) {
                    clearShare()
                    result.error("SHARE_FAILED", e.javaClass.simpleName, null)
                }
            } else if (call.method == "external") {
                try {
                    startActivity(Intent(Intent.ACTION_VIEW, Uri.parse("https://127.0.0.1:18443/api/health/live")))
                    result.success("browser_opened")
                } catch (e: Exception) {
                    result.error("BROWSER_UNAVAILABLE", e.javaClass.simpleName, null)
                }
            } else {
                worker.execute {
                    try {
                        val value = invoke(call)
                        runOnUiThread { result.success(value) }
                    } catch (e: Exception) {
                        // Deliberately exclude values, paths and URI contents from error logs.
                        runOnUiThread { result.error("M0_FAILURE", e.javaClass.simpleName, null) }
                    }
                }
            }
        }
    }

    private fun keyStore() = KeyStore.getInstance("AndroidKeyStore").apply { load(null) }
    private fun key(create: Boolean): SecretKey {
        val existing = keyStore().getKey(keyAlias, null) as? SecretKey
        if (existing != null) return existing
        check(create) { "Key unavailable; require new session" }
        return KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, "AndroidKeyStore").apply {
            init(KeyGenParameterSpec.Builder(keyAlias, KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT)
                .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
                .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
                .setKeySize(256).setRandomizedEncryptionRequired(true).build())
        }.generateKey()
    }
    private fun storeSecret(value: String) {
        require(value.toByteArray().size <= 4096)
        val cipher = Cipher.getInstance("AES/GCM/NoPadding")
        cipher.init(Cipher.ENCRYPT_MODE, key(true))
        cipher.updateAAD(keyAlias.toByteArray())
        val sealed = cipher.iv + cipher.doFinal(value.toByteArray(Charsets.UTF_8))
        val atomic = AtomicFile(secureFile)
        val output = atomic.startWrite()
        try { output.write(sealed); atomic.finishWrite(output) }
        catch (e: Exception) { atomic.failWrite(output); throw e }
    }
    private fun readSecret(): String? {
        if (!secureFile.exists()) return null
        val sealed = secureFile.readBytes()
        require(sealed.size in 28..4124)
        val cipher = Cipher.getInstance("AES/GCM/NoPadding")
        cipher.init(Cipher.DECRYPT_MODE, key(false), GCMParameterSpec(128, sealed.copyOfRange(0, 12)))
        cipher.updateAAD(keyAlias.toByteArray())
        return String(cipher.doFinal(sealed.copyOfRange(12, sealed.size)), Charsets.UTF_8)
    }
    private fun clearSecret() {
        AtomicFile(secureFile).delete()
        keyStore().deleteEntry(keyAlias)
    }
    private fun clearShare(): Boolean {
        sharedUri?.let { revokeUriPermission(it, Intent.FLAG_GRANT_READ_URI_PERMISSION) }
        sharedUri = null
        val file = File(cacheDir, "m0-share/synthetic.txt")
        if (file.exists()) check(file.delete())
        return !file.exists()
    }
    private fun invoke(call: MethodCall): Any? = when (call.method) {
        "secureWrite" -> { storeSecret(call.argument<String>("value")!!); true }
        "secureRead" -> readSecret()
        "secureClear" -> { clearSecret(); !secureFile.exists() && !keyStore().containsAlias(keyAlias) }
        "secureInfo" -> {
            val secret = key(false)
            val info = SecretKeyFactory.getInstance(secret.algorithm, "AndroidKeyStore")
                .getKeySpec(secret, KeyInfo::class.java) as KeyInfo
            mapOf("nonExportable" to (secret.encoded == null),
                "hardwareBacked" to info.isInsideSecureHardware,
                "securityLevel" to if (Build.VERSION.SDK_INT >= 31) info.securityLevel else -1,
                "backupExcluded" to (secureFile.parentFile == noBackupFilesDir))
        }
        "secureTamper" -> {
            val bytes = secureFile.readBytes()
            bytes[bytes.lastIndex] = (bytes.last().toInt() xor 1).toByte()
            secureFile.writeBytes(bytes); true
        }
        "secureDropKey" -> { keyStore().deleteEntry(keyAlias); true }
        "cacheWrite" -> {
            val scope = call.argument<String>("scope")!!
            require(scope in listOf("synthetic-a", "synthetic-b"))
            check(cache.edit().putString(scope, call.argument<String>("value")).commit()); true
        }
        "cacheRead" -> cache.getString(call.argument<String>("scope"), null)
        "cacheClear" -> { check(cache.edit().clear().commit()); true }
        "shareClear" -> clearShare()
        "uriDenied" -> {
            try {
                contentResolver.openInputStream(Uri.parse("content://com.android.externalstorage.documents/document/primary%3ADownload%2Fsoloops-denied.txt"))?.use { it.read() }
                false
            } catch (e: SecurityException) { true }
        }
        else -> error("Unknown diagnostic method")
    }

    @Deprecated("Platform callback retained to support the pinned Flutter embedding")
    override fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?) {
        super.onActivityResult(requestCode, resultCode, data)
        if (requestCode != 4101) return
        val result = picker ?: return
        picker = null
        if (resultCode != Activity.RESULT_OK || data?.data == null) {
            result.success(mapOf("status" to "cancelled")); return
        }
        val uri = data.data!!
        worker.execute {
            try {
                require(uri.scheme == "content")
                var name = "document"
                var declared = -1L
                contentResolver.query(uri, arrayOf(OpenableColumns.DISPLAY_NAME, OpenableColumns.SIZE), null, null, null)?.use {
                    if (it.moveToFirst()) { name = it.getString(0); if (!it.isNull(1)) declared = it.getLong(1) }
                }
                if (declared > maxBytes) throw IllegalArgumentException("Too large")
                val bytes = contentResolver.openInputStream(uri)!!.use { input ->
                    val output = ByteArrayOutputStream()
                    val buffer = ByteArray(64 * 1024)
                    while (true) {
                        val count = input.read(buffer)
                        if (count < 0) break
                        require(output.size() + count <= maxBytes) { "Too large" }
                        output.write(buffer, 0, count)
                    }
                    output.toByteArray()
                }
                val value = mapOf("status" to "selected", "name" to name,
                    "mime" to (contentResolver.getType(uri) ?: "application/octet-stream"),
                    "scheme" to uri.scheme, "bytes" to bytes,
                    "sha256" to MessageDigest.getInstance("SHA-256").digest(bytes).joinToString("") { "%02x".format(it) })
                runOnUiThread { result.success(value) }
            } catch (e: Exception) {
                runOnUiThread { result.error(if (e is IllegalArgumentException) "FILE_TOO_LARGE" else "FILE_READ_FAILED", e.javaClass.simpleName, null) }
            }
        }
    }
    override fun onDestroy() {
        picker?.error("ACTIVITY_DESTROYED", "Selection interrupted", null)
        picker = null
        worker.shutdown()
        super.onDestroy()
    }
}
