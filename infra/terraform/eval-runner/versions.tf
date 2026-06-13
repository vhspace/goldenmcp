terraform {
  required_version = ">= 1.14.0"

  required_providers {
    digitalocean = {
      source  = "digitalocean/digitalocean"
      version = "~> 2.89"
    }
  }
}

provider "digitalocean" {
  # Set via DIGITALOCEAN_TOKEN (scripts/terraform-apply-eval-runner.sh exports DO_API_KEY).
}
