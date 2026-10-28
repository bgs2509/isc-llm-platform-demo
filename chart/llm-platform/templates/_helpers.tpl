{{- define "llm-platform.labels" -}}
app.kubernetes.io/part-of: llm-platform
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end -}}
{{- define "llm-platform.modelBase" -}}http://{{ .Values.host.address }}:{{ .Values.host.modelPort }}{{- end -}}
{{- define "llm-platform.gpuBase" -}}http://{{ .Values.host.address }}:{{ .Values.host.gpuPort }}{{- end -}}
