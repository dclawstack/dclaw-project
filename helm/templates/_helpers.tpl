{{/* vim: set filetype=mustache: */}}

{{/*
Base name for all resources. Defaults to the chart name (dclaw-project) so the
rendered resource names match the live deployment exactly, independent of the
Helm release name.
*/}}
{{- define "dclaw-project.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Name of the app Secret consumed by the backend via envFrom.
*/}}
{{- define "dclaw-project.secretName" -}}
{{- default (printf "%s-secret" (include "dclaw-project.name" .)) .Values.secret.name }}
{{- end }}
