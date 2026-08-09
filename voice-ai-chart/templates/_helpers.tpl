{{- define "voice-ai.name" -}}
voice-ai
{{- end }}

{{- define "voice-ai.fullname" -}}
voice-ai
{{- end }}

{{- define "voice-ai-grpc.name" -}}
voice-ai-grpc
{{- end }}

{{- define "voice-ai-grpc.fullname" -}}
voice-ai-grpc
{{- end }}

{{- define "voice-ai-audio-worker.name" -}}
voice-ai-audio-worker
{{- end }}

{{- define "voice-ai-audio-worker.fullname" -}}
voice-ai-audio-worker
{{- end }}

{{- define "voice-ai-tts-worker.fullname" -}}
voice-ai-tts-worker
{{- end }}

{{- define "voice-ai-tts-worker.name" -}}
voice-ai-tts-worker
{{- end }}

{{- define "voice-ai.groqSecretName" -}}
{{- if .Values.groq.existingSecret -}}
{{- .Values.groq.existingSecret -}}
{{- else -}}
{{- printf "%s-groq" (include "voice-ai.fullname" .) -}}
{{- end -}}
{{- end }}

{{- define "voice-ai.googleSecretName" -}}
{{- if .Values.google.existingSecret -}}
{{- .Values.google.existingSecret -}}
{{- else -}}
{{- printf "%s-google" (include "voice-ai.fullname" .) -}}
{{- end -}}
{{- end }}