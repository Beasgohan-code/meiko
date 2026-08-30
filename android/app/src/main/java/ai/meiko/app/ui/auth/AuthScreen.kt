package ai.meiko.app.ui.auth

import android.annotation.SuppressLint
import android.webkit.WebResourceRequest
import android.webkit.WebView
import android.webkit.WebViewClient
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Close
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import ai.meiko.app.ui.theme.MeikoColors

/**
 * "Sign in with GitHub" screen: hosts the OAuth authorize page + callback
 * inside an in-app WebView (no Chrome Custom Tabs dependency needed).
 * `client_redirect=meiko://auth` (baked into [loginUrl]) makes the backend
 * bounce back to a URL this WebView intercepts before it ever navigates
 * there for real — that's how we pull the session token out of the
 * fragment without needing a real deep-link/intent-filter round trip.
 */
@SuppressLint("SetJavaScriptEnabled")
@Composable
fun AuthScreen(loginUrl: String, onToken: (String) -> Unit, onClose: () -> Unit) {
    Box(modifier = Modifier.fillMaxSize().background(MeikoColors.Bg0)) {
        AndroidView(
            modifier = Modifier.fillMaxSize(),
            factory = { ctx ->
                WebView(ctx).apply {
                    settings.javaScriptEnabled = true
                    settings.domStorageEnabled = true
                    webViewClient = object : WebViewClient() {
                        override fun shouldOverrideUrlLoading(
                            view: WebView,
                            request: WebResourceRequest,
                        ): Boolean {
                            val url = request.url.toString()
                            if (url.startsWith("meiko://auth")) {
                                val fragment = request.url.fragment // "token=..."
                                val token = fragment?.removePrefix("token=")
                                if (!token.isNullOrBlank()) onToken(java.net.URLDecoder.decode(token, "UTF-8"))
                                else onClose()
                                return true // don't actually navigate to the fake scheme
                            }
                            return false
                        }
                    }
                    loadUrl(loginUrl)
                }
            },
        )
        Column(modifier = Modifier.padding(12.dp), horizontalAlignment = Alignment.Start) {
            IconButton(onClick = onClose) {
                Icon(Icons.Filled.Close, contentDescription = "Cancel sign-in", tint = MeikoColors.Text1)
            }
        }
    }
}
