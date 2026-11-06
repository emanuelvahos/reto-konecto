package io.konecto.series76.ui.components

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.core.Spring
import androidx.compose.animation.core.spring
import androidx.compose.animation.fadeIn
import androidx.compose.animation.slideInVertically
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import io.konecto.series76.data.ActuatorDto
import io.konecto.series76.data.MessageRecord
import io.konecto.series76.data.Verification
import io.konecto.series76.ui.ProductDataVisualizer
import io.konecto.series76.ui.SuggestedFollowupRow
import io.konecto.series76.ui.VerificationBadge
import io.konecto.series76.ui.buildEffectiveActionChips
import io.konecto.series76.ui.theme.KonectoTheme
import io.konecto.series76.ui.theme.Spacing

@Composable
fun ChatBubbleItem(
    msg: MessageRecord,
    verification: Verification? = null,
    isLastAssistantMessage: Boolean = false,
    onSendQuery: (String) -> Unit = {},
    onRetry: () -> Unit = {},
    onOpenFullDatasheet: (ActuatorDto) -> Unit = {}
) {
    val isUser = msg.role == "user"
    val bubbleShape = if (isUser) {
        RoundedCornerShape(topStart = 16.dp, topEnd = 16.dp, bottomStart = 16.dp, bottomEnd = 4.dp)
    } else {
        RoundedCornerShape(topStart = 16.dp, topEnd = 16.dp, bottomStart = 4.dp, bottomEnd = 16.dp)
    }

    val semantics = KonectoTheme.semantics
    val onSurface = MaterialTheme.colorScheme.onSurface

    // En caso de aclaración donde answer == question, suprimir el duplicado de texto
    val isClarificationQuestionDuplicated = remember(msg) {
        val clar = msg.uiPayload?.clarification
        clar != null && clar.question.isNotBlank() && (
            msg.content.trim().equals(clar.question.trim(), ignoreCase = true) ||
            msg.uiPayload.displayType == "CLARIFICATION"
        )
    }

    val formattedContent = remember(msg.content, isUser, onSurface) {
        if (isUser) {
            AnnotatedString(msg.content)
        } else {
            parseCleanMarkdown(
                text = msg.content,
                textColor = onSurface,
                codeBgColor = semantics.codeBg,
                codeTextColor = semantics.codeText
            )
        }
    }

    var visible by remember { mutableStateOf(false) }
    LaunchedEffect(Unit) {
        visible = true
    }

    AnimatedVisibility(
        visible = visible,
        enter = fadeIn(
            animationSpec = spring(dampingRatio = Spring.DampingRatioNoBouncy, stiffness = Spring.StiffnessMedium)
        ) + slideInVertically(
            initialOffsetY = { 24 },
            animationSpec = spring(dampingRatio = Spring.DampingRatioNoBouncy, stiffness = Spring.StiffnessMedium)
        )
    ) {
        Column(
            modifier = Modifier.fillMaxWidth(),
            horizontalAlignment = if (isUser) Alignment.End else Alignment.Start
        ) {
            // Insignia de verificación (discreta verde-azulado para verified, sutil advertencia para fallback)
            // Mostrarla solo si verification.numbers_checked > 0 o ui_payload.actuators no está vacío
            if (!isUser && verification != null) {
                VerificationBadge(
                    verification = verification,
                    uiPayload = msg.uiPayload
                )
            }

            // Burbuja de texto (suprimida si es pregunta de aclaración para no duplicar con la tarjeta)
            if (formattedContent.text.isNotBlank() && !isClarificationQuestionDuplicated) {
                Box(
                    modifier = Modifier
                        .widthIn(max = 340.dp)
                        .clip(bubbleShape)
                        .then(
                            if (isUser) {
                                Modifier
                                    .background(semantics.accent)
                                    .border(1.dp, semantics.accent.copy(alpha = 0.8f), bubbleShape)
                            } else {
                                Modifier
                                    .background(MaterialTheme.colorScheme.surface)
                                    .border(1.dp, MaterialTheme.colorScheme.outline, bubbleShape)
                            }
                        )
                ) {
                    Text(
                        text = formattedContent,
                        color = if (isUser) semantics.onAccent else MaterialTheme.colorScheme.onSurface,
                        style = MaterialTheme.typography.bodyLarge,
                        lineHeight = 21.sp,
                        modifier = Modifier.padding(horizontal = Spacing.m, vertical = Spacing.s)
                    )
                }
            }

            // Visualizador estructurado (tarjetas, comparativas, recomendaciones, aclaraciones, alertas)
            if (!isUser && msg.uiPayload != null) {
                ProductDataVisualizer(
                    uiPayload = msg.uiPayload,
                    contextText = msg.content,
                    onSendQuery = onSendQuery,
                    onRetry = onRetry,
                    onOpenFullDatasheet = onOpenFullDatasheet
                )
            }

            // Chips deterministas de seguimiento / opciones interactivas de aclaración
            val effectiveChips = remember(msg.uiPayload) {
                buildEffectiveActionChips(msg.uiPayload)
            }
            if (!isUser && isLastAssistantMessage && effectiveChips.isNotEmpty()) {
                SuggestedFollowupRow(
                    followups = effectiveChips,
                    onSelect = onSendQuery
                )
            }
        }
    }
}
