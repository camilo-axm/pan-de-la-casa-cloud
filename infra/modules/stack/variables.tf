variable "environment" {
  description = "Ambiente: dev o prod."
  type        = string

  validation {
    condition     = contains(["dev", "prod"], var.environment)
    error_message = "El ambiente debe ser dev o prod."
  }
}

variable "location" {
  description = "Region permitida por la politica de la suscripcion."
  type        = string
}

variable "container_app_environment_id" {
  description = "Ambiente de Container Apps compartido, creado por infra/environments/shared."
  type        = string
}

variable "image" {
  description = "Imagen fijada por digest, para que prod ejecute exactamente lo probado en dev."
  type        = string

  validation {
    condition     = can(regex("@sha256:[a-f0-9]{64}$", var.image))
    error_message = "La imagen debe fijarse por digest: registro/imagen@sha256:..."
  }
}

variable "min_replicas" {
  description = "Replicas minimas. Con 0 la app escala a cero."
  type        = number
  default     = 0
}

variable "max_replicas" {
  description = "Tope de replicas."
  type        = number
  default     = 1

  validation {
    condition     = var.max_replicas >= 1 && var.max_replicas <= 5
    error_message = "max_replicas debe estar entre 1 y 5 para proteger el presupuesto."
  }
}

variable "cosmos_free_tier" {
  description = "Usa la capa gratuita de Cosmos DB. Solo una cuenta por suscripcion puede tenerla."
  type        = bool
  default     = false
}

variable "alert_email" {
  description = "Correo que recibe las alertas. Con null no se crean alertas ni presupuesto."
  type        = string
  default     = null
}

variable "owner_email" {
  description = "Correo de la cuenta inicial del dueño."
  type        = string
  default     = ""
}

variable "owner_password" {
  description = "Contraseña inicial del dueño."
  type        = string
  default     = ""
  sensitive   = true

  validation {
    condition = (
      (var.owner_email == "" && var.owner_password == "") ||
      (can(regex("^[^@[:space:]]+@[^@[:space:]]+$", var.owner_email)) && length(var.owner_password) >= 10)
    )
    error_message = "Configura juntos un correo válido y una contraseña de al menos 10 caracteres, o deja ambos vacíos."
  }
}

variable "alert_5xx_threshold" {
  description = "Errores 5xx en 5 minutos que disparan la alerta."
  type        = number
  default     = 5
}

variable "monthly_budget_usd" {
  description = "Presupuesto mensual del ambiente."
  type        = number
  default     = 20
}

variable "budget_start_date" {
  description = "Primer dia del mes en que empieza el presupuesto."
  type        = string
  default     = "2026-11-01T00:00:00Z"
}

variable "rbac_propagation_wait" {
  description = "Espera tras cada asignacion de rol."
  type        = string
  default     = "90s"
}
