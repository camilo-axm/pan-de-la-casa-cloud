variable "account_name" {
  description = "Nombre global de la cuenta de Cosmos DB."
  type        = string

  validation {
    condition     = can(regex("^[a-z0-9][a-z0-9-]{1,42}[a-z0-9]$", var.account_name))
    error_message = "Usa de 3 a 44 caracteres en minusculas, numeros y guiones."
  }
}

variable "resource_group_name" {
  description = "Grupo de recursos."
  type        = string
}

variable "location" {
  description = "Region de Azure."
  type        = string
}

variable "database_name" {
  description = "Base de datos de la aplicacion."
  type        = string
  default     = "panaderia"
}

variable "free_tier" {
  description = "Usa la capa gratuita con autoescala. Con false la cuenta es serverless."
  type        = bool
  default     = false
}

variable "tags" {
  description = "Etiquetas."
  type        = map(string)
  default     = {}
}
