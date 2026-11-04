package io.konecto.series76.data

import com.jakewharton.retrofit2.converter.kotlinx.serialization.asConverterFactory
import kotlinx.serialization.json.Json
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.logging.HttpLoggingInterceptor
import retrofit2.Retrofit
import retrofit2.http.*
import java.util.concurrent.TimeUnit

interface Series76Api {
    @GET("health")
    suspend fun healthCheck(): HealthResponse

    @POST("api/auth/login")
    suspend fun login(@Body request: LoginRequest): LoginResponse

    @POST("api/conversation")
    suspend fun sendMessage(@Body request: ConversationRequest): ConversationResponse

    @GET("api/sessions")
    suspend fun getSessions(): List<SessionSummary>

    @GET("api/sessions/{sessionId}/messages")
    suspend fun getSessionHistory(@Path("sessionId") sessionId: String): SessionHistoryResponse

    @DELETE("api/sessions/{sessionId}")
    suspend fun deleteSession(@Path("sessionId") sessionId: String)
}

object ApiClient {
    var authToken: String? = null
    var baseUrl: String = "http://10.0.2.2:8001/"
        set(value) {
            field = if (value.endsWith("/")) value else "$value/"
            rebuildRetrofit()
        }

    val jsonFormat = Json {
        ignoreUnknownKeys = true
        coerceInputValues = true
        isLenient = true
        prettyPrint = true
    }

    private var apiInstance: Series76Api? = null

    val api: Series76Api
        get() {
            if (apiInstance == null) rebuildRetrofit()
            return apiInstance!!
        }

    private fun rebuildRetrofit() {
        val logging = HttpLoggingInterceptor().apply {
            level = HttpLoggingInterceptor.Level.BASIC
        }

        val client = OkHttpClient.Builder()
            .connectTimeout(15, TimeUnit.SECONDS)
            .readTimeout(45, TimeUnit.SECONDS)
            .writeTimeout(45, TimeUnit.SECONDS)
            .addInterceptor(logging)
            .addInterceptor { chain ->
                val reqBuilder = chain.request().newBuilder()
                authToken?.let { token ->
                    if (token.isNotBlank()) {
                        reqBuilder.addHeader("Authorization", "Bearer $token")
                    }
                }
                chain.proceed(reqBuilder.build())
            }
            .build()

        val contentType = "application/json".toMediaType()
        apiInstance = Retrofit.Builder()
            .baseUrl(baseUrl)
            .client(client)
            .addConverterFactory(jsonFormat.asConverterFactory(contentType))
            .build()
            .create(Series76Api::class.java)
    }

    suspend fun testConnection(targetUrl: String): Result<HealthResponse> {
        return try {
            val url = if (targetUrl.endsWith("/")) targetUrl else "$targetUrl/"
            val testClient = OkHttpClient.Builder()
                .connectTimeout(5, TimeUnit.SECONDS)
                .readTimeout(5, TimeUnit.SECONDS)
                .build()
            val contentType = "application/json".toMediaType()
            val testApi = Retrofit.Builder()
                .baseUrl(url)
                .client(testClient)
                .addConverterFactory(jsonFormat.asConverterFactory(contentType))
                .build()
                .create(Series76Api::class.java)
            val resp = testApi.healthCheck()
            Result.success(resp)
        } catch (e: Exception) {
            Result.failure(e)
        }
    }
}
