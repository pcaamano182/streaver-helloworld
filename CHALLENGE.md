# DevOps/SRE Challenge - Streaver

## Challenge Overview

In this challenge, we want to assess how you design, reason about, and implement a minimal but production-ready cloud setup on AWS. The focus is not on building complex application logic, but on infrastructure quality, automation, resilience, and security.

You'll build and deploy a small containerized application, expose it publicly, and demonstrate how you think about operating it safely and reliably in the real world.

There is no single "correct" solution. What matters is your ability to make sensible trade-offs and clearly explain them.

## Step 1 – Application

Create a minimal containerized application (language and framework of your choice).

The app must:
- Expose an HTTP endpoint accessible over the public internet
- Include at least one endpoint that intentionally returns a 5XX error (to validate observability and alerting)
- Be simple by design (a "hello world" is enough)
- Provide a Dockerfile at the root of the repository

## Step 2 – Infrastructure as Code

Provision all infrastructure using AWS CDK.

At a minimum, your setup should include:
- An ECS service running your containerized app
- Internet access for the service (ALB or equivalent)
- Proper networking setup (VPC, subnets, security groups)
- IAM roles with minimal required permissions

The code should be readable, well-structured, and easy to extend.

## Step 3 – Resilience and Scalability

Design the system so it can:
- Recover from failures automatically
- Scale based on load (e.g. CPU, memory, or request count)

You're free to choose scaling signals and thresholds. If something is not explicitly defined, document your assumptions.

## Step 4 – Operational Visibility

Make it possible to understand how the system behaves in production.

At a minimum:
- Application logs should be accessible
- Basic metrics (CPU, memory, request health) should be available
- Alerts should be configured for service degradation or high resource usage

We're not looking for perfection here—just a solid, pragmatic baseline.

## Step 5 – Security by Default

Apply security best practices out of the box:
- Least-privilege IAM
- Secure communication where applicable
- No unintended public exposure
- Sensible defaults over convenience

If you intentionally skip something, explain why.

## Step 6 – Automation Pipeline (Optional)

Optionally, add a CI/CD pipeline using GitHub Actions or CircleCI that:
- Builds the container image
- Deploys infrastructure and application changes
- Requires minimal manual intervention

This is optional, but a strong signal if done well.

## Deliverables

A private GitHub repository containing:

- AWS CDK infrastructure code
- Dockerfile for the app
- Optional CI/CD configuration
- **README.md** including:
  - How to deploy the system
  - How to destroy/clean up resources
  - What you would improve with more time
- **ASSUMPTIONS.md**
  - Document all assumptions, trade-offs, and rationale behind key decisions

---

**Company**: Streaver
**Position**: Senior DevOps/SRE Engineer
