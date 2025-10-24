# Simple monitor script
param(
    [string]$Service = "all"
)

switch ($Service) {
    "trainer" {
        docker-compose logs -f trainer
    }
    "processor" {
        docker-compose logs -f processor
    }
    "downloader" {
        docker-compose logs -f downloader
    }
    "status" {
        docker-compose ps
    }
    default {
        docker-compose logs -f
    }
}