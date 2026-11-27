variable "name" {
  description = "Sufijo comun de los recursos."
  type        = string
}

variable "resource_group_name" {
  description = "Grupo de recursos."
  type        = string
}

variable "location" {
  description = "Region de Azure."
  type        = string
}

variable "environment_id" {
  description = "Ambiente de Container Apps donde se publica la app."
  type        = string
}

variable "image" {
  description = "Imagen del contenedor."
  type        = string
}

variable "key_vault_id" {
  description = "Key Vault del que la app lee secretos."
  type        = string
}

variable "secret_ids" {
  description = "Debe incluir mongodb-uri y admin-api-key."
  type        = map(string)

  validation {
    condition     = alltrue([for name in ["mongodb-uri", "admin-api-key"] : contains(keys(var.secret_ids), name)])
    error_message = "secret_ids debe incluir mongodb-uri y admin-api-key."
  }
}

variable "environment_variables" {
  description = "Variables de entorno no secretas."
  type        = map(string)
  default     = {}
}

variable "container_apps_express" {
  description = "Indica que la app se publica en un entorno Express."
  type        = bool
  default     = false
}

variable "secret_values" {
  description = "Valores sensibles para los secretos nativos de Container Apps en modo Express."
  type        = map(string)
  sensitive   = true
  default     = {}
}

variable "min_replicas" {
  description = "Con 0 la app escala a cero y no consume computo sin trafico."
  type        = number
  default     = 0
}

variable "max_replicas" {
  description = "Tope de replicas; limita tambien el costo maximo."
  type        = number
  default     = 1
}

variable "rbac_propagation_wait" {
  description = "Espera tras asignar el rol de lectura."
  type        = string
  default     = "90s"
}

variable "tags" {
  description = "Etiquetas."
  type        = map(string)
  default     = {}
}
