package io.konecto.series76.ui.components

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import io.konecto.series76.data.MessageRecord
import io.konecto.series76.ui.ProductDataVisualizer
import io.konecto.series76.ui.theme.KonectoTheme
import io.konecto.series76.ui.theme.Spacing

@Composable
fun ChatBubbleItem(msg: MessageRecord) {
    val isUser = msg.role == "user"
    val bubbleShape = if (isUser) {
        RoundedCornerShape(topStart = 16.dp, topEnd = 16.dp, bottomStart = 16.dp, bottomEnd = 4.dp)
    } else {
        RoundedCornerShape(topStart = 16.dp, topEnd = 16.dp, bottomStart = 4.dp, bottomEnd = 16.dp)
    }

    val semantics = KonectoTheme.semantics
    val onSurface = MaterialTheme.colorScheme.onSurface
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

    Column(
        modifier = Modifier.fillMaxWidth(),
        horizontalAlignment = if (isUser) Alignment.End else Alignment.Start
    ) {
        if (formattedContent.text.isNotBlank()) {
            Box(
                modifier = Modifier
                    .widthIn(max = 340.dp)
                    .clip(bubbleShape)
                    .then(
                        if (isUser) {
                            Modifier.background(MaterialTheme.colorScheme.primary)
                        } else {
                            Modifier
                                .background(MaterialTheme.colorScheme.surface)
                                .border(1.dp, MaterialTheme.colorScheme.outline, bubbleShape)
                        }
                    )
            ) {
                Text(
                    text = formattedContent,
                    color = if (isUser) MaterialTheme.colorScheme.onPrimary else MaterialTheme.colorScheme.onSurface,
                    style = MaterialTheme.typography.bodyLarge,
                    lineHeight = 21.sp,
                    modifier = Modifier.padding(horizontal = Spacing.m, vertical = Spacing.s)
                )
            }
        }

        if (!isUser && msg.uiPayload != null) {
            ProductDataVisualizer(
                uiPayload = msg.uiPayload,
                contextText = msg.content
            )
        }
    }
}

