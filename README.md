# ELD Route Planner Backend

## Overview

This project is a **Django-based backend service** designed for **ELD (Electronic Logging Device) Route Planning**. It provides an intelligent routing engine that calculates compliant truck routes, taking into account **Hours of Service (HOS)** regulations.

The system simulates truck journeys day-by-day, automatically scheduling:
*   **Driving periods** (max 11 hours)
*   **On-duty limits** (max 14 hours)
*   **Mandatory breaks** (30 minutes after 8 hours of continuous driving)
*   **Sleeper berth/Off-duty time** (10 hours daily reset)
*   **Fueling stops**

It integrates with **OpenRouteService** for accurate geocoding and truck-specific routing data.

## Features

*   **Smart Route Simulation**: detailed day-by-day itinerary generation.
*   **HOS Compliance**: Enforces FMCSA Hours of Service rules.
*   **Geocoding & Routing**: Integration with OpenRouteService API.
*   **User Management**: JWT-based authentication and user profiles.
*   **Dockerized**: Fully containerized environment for easy deployment.

## Tech Stack

*   **Language**: Python 3.10+
*   **Framework**: Django 4.1, Django REST Framework (DRF)
*   **Database**: PostgreSQL
*   **Containerization**: Docker, Docker Compose
*   **External APIs**: OpenRouteService

## Getting Started

### Prerequisites

*   [Docker](https://www.docker.com/)
*   [Docker Compose](https://docs.docker.com/compose/)

### Configuration

1.  Clone the repository.
2.  Create a `.env` file in the root directory (or `backend/` depending on your setup, usually root for docker-compose).
3.  Add your OpenRouteService API key and other settings:

```env
OPEN_ROUTE_API_KEY=your_api_key_here
SECRET_KEY=your_django_secret_key
DEBUG=True
ALLOWED_HOSTS=*
# Database settings (if not using default docker-compose values)
POSTGRES_DB=eld_db
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_HOST=db
POSTGRES_PORT=5432
```

### Running the Project

Use the provided `Makefile` for common tasks:

*   **Start the services**:
    ```bash
    make up
    ```

*   **Stop the services**:
    ```bash
    make stop
    ```

*   **View logs**:
    ```bash
    make logs
    ```

*   **Run migrations**:
    ```bash
    make migrate
    ```

*   **Create a superuser** (access container shell):
    ```bash
    make shell
    # inside shell: python manage.py createsuperuser
    ```

## API Documentation

The API documentation is automatically generated using `drf-spectacular`. Once the server is running (usually at `http://localhost:8001`), you can access:

*   **Swagger UI**: [`/api/schema/swagger/`](http://localhost:8001/api/schema/swagger/)
*   **Redoc**: [`/api/schema/redoc/`](http://localhost:8001/api/schema/redoc/)

## Project Structure

*   `backend/apps/core`: Contains the core logic for route planning and services.
*   `backend/apps/users`: User management and authentication.
*   `backend/config`: Project-wide settings and URL configurations.
