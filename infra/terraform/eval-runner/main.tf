data "digitalocean_ssh_key" "operator" {
  for_each = toset(var.ssh_key_names)
  name     = each.value
}

resource "digitalocean_droplet" "eval_runner" {
  name     = var.droplet_name
  region   = var.region
  size     = var.droplet_size
  image    = var.image
  ssh_keys = [for k in data.digitalocean_ssh_key.operator : k.fingerprint]
  tags     = var.tags

  user_data = templatefile("${path.module}/cloud-init.yaml.tftpl", {
    repo_url          = var.repo_url
    repo_branch       = var.repo_branch
    repo_install_path = var.repo_install_path
  })

  lifecycle {
    create_before_destroy = true
  }
}

resource "digitalocean_firewall" "eval_runner" {
  name = "${var.droplet_name}-fw"

  droplet_ids = [digitalocean_droplet.eval_runner.id]

  inbound_rule {
    protocol         = "tcp"
    port_range       = "22"
    source_addresses = ["0.0.0.0/0", "::/0"]
  }

  inbound_rule {
    protocol         = "tcp"
    port_range       = "80"
    source_addresses = var.allowed_https_cidrs
  }

  inbound_rule {
    protocol         = "tcp"
    port_range       = "443"
    source_addresses = var.allowed_https_cidrs
  }

  outbound_rule {
    protocol              = "tcp"
    port_range            = "1-65535"
    destination_addresses = ["0.0.0.0/0", "::/0"]
  }

  outbound_rule {
    protocol              = "udp"
    port_range            = "1-65535"
    destination_addresses = ["0.0.0.0/0", "::/0"]
  }

  outbound_rule {
    protocol              = "icmp"
    destination_addresses = ["0.0.0.0/0", "::/0"]
  }
}
