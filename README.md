# DevOps Test Assignment Documentation

## Table of Contents

1. [Introduction](#introduction)
2. [Infrastructure Setup](#infrastructure-setup)
   - [VPC Configuration](#vpc-configuration)
   - [MySQL RDS Instance](#mysql-rds-instance)
   - [ElastiCache Redis Instance](#elasticache-redis-instance)
   - [EC2 Instance](#ec2-instance)
3. [Application Deployment](#application-deployment)
   - [WordPress Installation](#wordpress-installation)
   - [Configuration Details](#configuration-details)
4. [Deployment Scripts](#deployment-scripts)
5. [External Modules and Tools](#external-modules-and-tools)
6. [Code Structure Overview](#code-structure-overview)
7. [Configuration Options](#configuration-options)
8. [Troubleshooting and Common Issues](#troubleshooting-and-common-issues)

## Introduction

This project demonstrates the deployment of a typical web application infrastructure on AWS using Terraform for Infrastructure as Code (IaC) and bash scripts for application deployment. The setup includes:

- A Virtual Private Cloud (VPC)
- A MySQL RDS instance
- An ElastiCache Redis instance
- An EC2 instance hosting a WordPress application

## Infrastructure Setup

All infrastructure components are defined using Terraform configurations located in the repository.

### VPC Configuration

The VPC is configured to host the necessary subnets, route tables, and security groups required for the application.

### MySQL RDS Instance

- **Configuration**: The RDS instance is set up with the following parameters:
  - Engine: MySQL
  - Accessibility: Private (not reachable from the public internet)

### ElastiCache Redis Instance

- **Configuration**: The Redis instance is configured as follows:
  - Engine: Redis
  - Accessibility: Private (not reachable from the public internet)

### EC2 Instance

- **Configuration**:
  - Instance Type: `t2.micro` (eligible for AWS Free Tier)
  - Accessibility: Public (reachable from the internet)

## Application Deployment

### WordPress Installation

WordPress is deployed on the EC2 instance using a custom bash deployment script.

### Configuration Details

- **Database Connection**:
  - The WordPress application connects to the MySQL RDS instance using environment variables for database credentials and endpoints.
- **Session Management**:
  - WordPress sessions are managed using the ElastiCache Redis instance, with connection details provided via environment variables.

## Deployment Scripts

The deployment process is automated using a bash script that performs the following tasks:

1. Installs necessary dependencies (e.g., Apache, PHP)
2. Downloads and configures WordPress
3. Sets up environment variables for database and Redis connections
4. Starts the web server

The deployment script is located in the `bootstrap` directory of the repository.

## External Modules and Tools

- **Terraform AWS VPC Module**:
  - Source: [terraform-aws-modules/vpc/aws](https://registry.terraform.io/modules/terraform-aws-modules/vpc/aws)
  - **Reason for Use**: Simplifies VPC creation and management by providing a well-tested and community-supported module.

- **Terraform AWS EC2 Instance Module**:
  - Source: [terraform-aws-modules/ec2-instance/aws](https://registry.terraform.io/modules/terraform-aws-modules/ec2-instance/aws)
  - **Reason for Use**: Provides a flexible and easy way to provision EC2 instances with common configurations.

## Code Structure Overview

The repository is organized as follows:

- `bootstrap/`: Contains the bash deployment script for WordPress.
- `modules/`: Includes custom Terraform modules used in the infrastructure setup.
- `vpc/`: Contains Terraform configurations specific to VPC setup.
- `.gitignore`: Specifies files and directories to be ignored by git.
- `README.md`: Provides an overview and instructions for the project.

## Configuration Options

- **Terraform Variables**:
  - Variables for customizing the infrastructure (e.g., instance types, database settings) are defined in the Terraform configuration files.

- **Deployment Script Parameters**:
  - The bash script accepts environment variables for database and Redis connection details, allowing for customization without modifying the script.

## Troubleshooting and Common Issues

- **Issue**: EC2 instance not reachable.
  - **Solution**: Verify that the security group associated with the EC2 instance allows inbound traffic on the required ports (e.g., 80 for HTTP).

- **Issue**: WordPress cannot connect to the database.
  - **Solution**: Ensure that the RDS instance is accessible from the EC2 instance and that the correct environment variables are set for database credentials.

- **Issue**: Sessions not persisting.
  - **Solution**: Check the connection to the Redis instance and verify that the appropriate PHP extensions for Redis are installed.

For more detailed information, refer to the comments within the Terraform configuration files and the deployment script.