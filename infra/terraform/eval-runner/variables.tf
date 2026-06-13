variable "region" {
  description = "DigitalOcean region slug"
  type        = string
  default     = "nyc3"
}

variable "droplet_size" {
  description = "Droplet size slug (8 GB RAM default for Inspect + npx MCP stdio servers)"
  type        = string
  default     = "s-4vcpu-8gb"
}

variable "droplet_name" {
  description = "Droplet hostname"
  type        = string
  default     = "goldenmcp-eval-runner"
}

variable "image" {
  description = "Droplet base image slug"
  type        = string
  default     = "ubuntu-24-04-x64"
}

variable "ssh_key_name" {
  description = "Name for the SSH key resource created in DigitalOcean"
  type        = string
  default     = "goldenmcp-eval-runner"
}

variable "ssh_public_key" {
  description = "Operator SSH public key contents (e.g. contents of ~/.ssh/id_ed25519.pub)"
  type        = string
  sensitive   = true
}

variable "allowed_ssh_cidrs" {
  description = "CIDR blocks allowed to SSH (port 22) to the droplet"
  type        = list(string)
}

variable "allowed_https_cidrs" {
  description = "CIDR blocks allowed to reach HTTPS (443) for eval-runner API"
  type        = list(string)
  default     = ["0.0.0.0/0", "::/0"]
}

variable "repo_url" {
  description = "Git repository URL cloned onto the droplet"
  type        = string
  default     = "https://github.com/vhspace/goldenmcp.git"
}

variable "repo_branch" {
  description = "Git branch checked out on the droplet"
  type        = string
  default     = "main"
}

variable "repo_install_path" {
  description = "Filesystem path for the goldenmcp checkout"
  type        = string
  default     = "/opt/goldenmcp"
}

variable "tags" {
  description = "Tags applied to the droplet and firewall"
  type        = list(string)
  default     = ["goldenmcp", "eval-runner"]
}
