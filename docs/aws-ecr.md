# AWS ECR

# Current Repositories

| Repository name | URI | Image Tag |
| :---- | :---- | :---- |
| ggezlabs/hummingbot | public.ecr.aws/s2m1f3k2/ggezlabs/hummingbot | 2.7.0 |
| ggezlabs/hummingbot-backend-api | public.ecr.aws/s2m1f3k2/ggezlabs/hummingbot-backend-api | 2.7.0 |
| ggezlabs/hummingbot-dashboard | public.ecr.aws/s2m1f3k2/ggezlabs/hummingbot-dashboard | 2.7.0 |
| ggezlabs/hummingbot-gateway | public.ecr.aws/s2m1f3k2/ggezlabs/hummingbot-gateway | 2.7.0 |

# Amazon Elastic Container Registry (ECR) – Docker Image Push & Pull Guide

This guide explains how to upload Docker images to **AWS ECR** and pull them on other devices.

## 1. Create an AWS Account

Sign up for an AWS account if you don't already have one: [https://aws.amazon.com](https://aws.amazon.com/)

## 2. Create an IAM User

* Create a new IAM user for Docker/ECR access.

* Assign permissions to access **ECR**. For example, use the **AmazonEC2ContainerRegistryFullAccess** policy.

## 3. Generate Access Keys

* Go to **Security Credentials** in the IAM console.

* Create an **Access Key** for the IAM user.

* Note the **Access Key ID** and **Secret Access Key** — you'll need them for AWS CLI configuration.

## 4. Create a Repository in ECR

* Go to **Amazon ECR → Repositories → Create Repository**.

* Choose either **Public** or **Private** depending on your use case.

## 5. Install AWS CLI on Local Device

Run the following commands to install the AWS CLI (Linux example):

*curl "https://awscli.amazonaws.com/awscli-exe-linux-x86\_64.zip" \-o "awscliv2.zip"*

*unzip awscliv2.zip*

*sudo ./aws/install*

* Verify installation:

*aws \--version*

## 6. Configure AWS CLI

Run:

*aws configure*

You'll be prompted for:

AWS Access Key ID \[None\]: YOUR\_ACCESS\_KEY

AWS Secret Access Key \[None\]: YOUR\_SECRET\_KEY

Default region name \[None\]: us-east-1

Default output format \[None\]: json

## 7. Authenticate Docker with ECR

For **public ECR repositories**, run:

*aws ecr-public get-login-password \--region us-east-1 | docker login \--username AWS \--password-stdin public.ecr.aws*

**Note:** This logs Docker into ECR. You may see a warning about credentials being stored unencrypted — it's safe for development.

## 8. Build Your Local Docker Image

docker compose build

## 9. Tag Your Docker Image

Tag the image using the URI of your ECR repository:

docker tag myapp:latest public.ecr.aws/\<alias\>/\<repository\>:\<tag\>

* Replace `<alias>` and `<repository>` with the values from your ECR URI.

* `<tag>` is the version of your image (default: `latest`).

## 10. Push the Docker Image to ECR

docker push public.ecr.aws/\<alias\>/\<repository\>:\<tag\>

* Docker uploads only the layers that have changed.

## 11. Pull the Image from Another Device

### Option A – Using Docker CLI

1. Authenticate Docker on the new device:

aws ecr-public get-login-password \--region us-east-1 | docker login \--username AWS \--password-stdin public.ecr.aws

2. Pull the image:

docker pull public.ecr.aws/\<alias\>/\<repository\>:\<tag\>

### Option B – Using Docker Compose

1. Update your `docker-compose.yml` file:

image: public.ecr.aws/\<alias\>/\<repository\>:\<tag\>

2. Pull and start the container:

docker compose pull

docker compose up \-d

## 12. Update Docker Image on a Server

### Option A – Docker CLI

docker pull public.ecr.aws/\<alias\>/\<repository\>:\<tag\>

docker stop my\_container

docker rm my\_container

docker run \-d \--name my\_container public.ecr.aws/\<alias\>/\<repository\>:\<tag\>

### Option B – Docker Compose

docker compose pull

docker compose up \-d

Docker Compose automatically replaces the old container with the updated image.
