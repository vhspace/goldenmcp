output "droplet_id" {
  description = "DigitalOcean droplet ID"
  value       = digitalocean_droplet.eval_runner.id
}

output "droplet_ip" {
  description = "Public IPv4 address of the eval-runner droplet"
  value       = digitalocean_droplet.eval_runner.ipv4_address
}

output "droplet_urn" {
  description = "DigitalOcean URN for the droplet"
  value       = digitalocean_droplet.eval_runner.urn
}

output "health_check_url" {
  description = "HTTPS health endpoint (self-signed cert on first boot)"
  value       = "https://${digitalocean_droplet.eval_runner.ipv4_address}/health"
}

output "ssh_command" {
  description = "SSH to the droplet as root"
  value       = "ssh root@${digitalocean_droplet.eval_runner.ipv4_address}"
}

output "sync_secrets_command" {
  description = "Copy local .env secrets to the droplet after apply"
  value       = "../../../scripts/sync-eval-runner-secrets.sh ${digitalocean_droplet.eval_runner.ipv4_address}"
}
