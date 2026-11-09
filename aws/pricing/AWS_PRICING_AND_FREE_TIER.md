# CloudOps Sentinel: AWS Pricing, Free-Tier & Cost Optimization Guide 💰

This document provides a comprehensive cost model, AWS Free Tier breakdown, and operational guardrails for deploying **CloudOps Sentinel** to Amazon Web Services (AWS).

---

## 1. AWS Free Tier Eligibility Matrix

AWS provides two types of free tier benefits: **12 Months Free** (for new AWS accounts within their first year) and **Always Free** (available indefinitely to all accounts).

| AWS Service | Free Tier Category | Monthly Free Allocation | Sentinel Resource Mapping | Incurred Cost on Free Tier |
| :--- | :--- | :--- | :--- | :--- |
| **Amazon EC2** | 12 Months Free | **750 hours/month** of `t2.micro` or `t3.micro` Linux instances | Single EC2 host running Docker Compose stack | **\$0.00** *(1 instance running 24/7)* |
| **Amazon EBS** | 12 Months Free | **30 GB** General Purpose SSD (`gp2` or `gp3`) storage + 2M I/Os | EC2 root OS disk (20 GB allocated) | **\$0.00** |
| **Amazon RDS** | 12 Months Free | **750 hours/month** of Single-AZ `db.t2.micro` or `db.t3.micro` | Dedicated PostgreSQL 16 metadata database | **\$0.00** *(1 DB running 24/7)* |
| **RDS Storage**| 12 Months Free | **20 GB** SSD storage + **20 GB** automated backup storage | Database disk & automated RDS snapshots | **\$0.00** |
| **Amazon S3** | 12 Months Free | **5 GB** Standard S3 storage + 20,000 GETs + 2,000 PUTs | Compressed database dumps (`.dump.gz`) | **\$0.00** *(with 7-day retention)* |
| **S3 VPC Endpoint**| Always Free | **Unlimited** requests & bandwidth | Gateway VPC Endpoint attached to route tables | **\$0.00** |
| **CloudWatch** | Always Free | **10 Custom Metrics**, 3 Dashboards, 10 Alarms, **5 GB** Log Ingestion | Host & database metrics + container log streams | **\$0.00** |
| **SSM Parameter Store**| Always Free | **Unlimited standard parameters** + 10,000 API calls/sec | DB passwords, JWT secret keys, API credentials | **\$0.00** |
| **AWS SSM Session Mgr**| Always Free | **Unlimited** interactive terminal sessions | Zero-port-22 secure terminal access | **\$0.00** |

---

## 2. Architecture Cost Comparison

### Architecture A: 100% Free-Tier Dev / Staging Architecture
Designed for evaluation, local-to-cloud testing, and certification environments:
- **Compute:** 1x `t3.micro` EC2 instance (750 hrs/mo) = **\$0.00**
- **EBS:** 20 GB `gp3` root volume = **\$0.00**
- **Database:** 1x `db.t3.micro` Single-AZ RDS PostgreSQL 16 (750 hrs/mo) = **\$0.00**
- **RDS Storage:** 20 GB `gp3` = **\$0.00**
- **S3 Backups:** 2 GB average compressed retention = **\$0.00**
- **Secrets:** AWS Systems Manager (SSM) Parameter Store Standard = **\$0.00**
- **Networking:** Direct Public Subnet with strict Security Group (no NAT Gateway) = **\$0.00**
- **Total Estimated Monthly Cost:** **\$0.00 / month**

> [!NOTE]
> AWS recently instituted a \$0.005/hour charge for public IPv4 addresses (~**\$3.65/month**). To maintain a pure \$0.00 footprint, access the instance via **AWS Systems Manager Session Manager** (no public IP required if using SSM VPC endpoints or IPv6).

---

### Architecture B: Enterprise Production High-Availability (HA) Architecture
Designed for production multi-tenant workloads with 99.99% uptime SLAs:
- **Load Balancer:** AWS Application Load Balancer (ALB) across 2 AZs $\approx$ **\$22.50 / month**
- **Compute:** 2x `t4g.small` (2 vCPU, 2 GB RAM) behind Auto Scaling $\approx$ **\$24.50 / month**
- **Database:** `db.m6g.large` (2 vCPU, 8 GB RAM) Multi-AZ RDS PostgreSQL $\approx$ **\$142.00 / month**
- **Storage:** 100 GB `gp3` provisioned storage $\approx$ **\$11.50 / month**
- **NAT Gateways:** 2x Managed NAT Gateways (for private app subnets) $\approx$ **\$65.00 / month**
- **AWS Secrets Manager:** 2 secrets + automatic rotation $\approx$ **\$0.80 / month**
- **Total Estimated Monthly Cost:** **\$266.30 / month**

---

## 3. Critical Cost Pitfalls & How Sentinel Prevents Them

### ⚠️ Pitfall 1: The "750-Hour" Concurrency Trap
- **The Risk:** AWS allocates 750 free hours per month for EC2 and 750 free hours for RDS. If you run **two** `t3.micro` instances at the same time, you consume 1,500 hours in a 30-day month, resulting in 750 paid hours billed to your credit card.
- **Sentinel Mitigation:** Sentinel orchestrates all 6 platform microservices (Frontend, Backend, Prometheus, Grafana, Alertmanager, Postgres Exporter) onto **one single EC2 instance** using Docker Compose.

### ⚠️ Pitfall 2: AWS Managed NAT Gateways
- **The Risk:** A standard AWS NAT Gateway costs **\$0.045 per hour** plus **\$0.045 per GB processed**. Running 2 NAT Gateways for multi-AZ private subnets costs approximately **\$65/month even if zero traffic passes through them**.
- **Sentinel Mitigation:**
  1. Utilizes **S3 Gateway VPC Endpoint** (attached directly to VPC route tables at **\$0.00 cost**).
  2. In the Free-Tier CloudFormation profile, the EC2 instance resides in the Public Subnet with Internet Gateway egress, entirely eliminating the NAT Gateway requirement.

### ⚠️ Pitfall 3: AWS Secrets Manager vs. SSM Parameter Store
- **The Risk:** AWS Secrets Manager charges **\$0.40 per secret per month** + \$0.05 per 10,000 API requests after the 30-day trial.
- **Sentinel Mitigation:** Sentinel's bootstrap scripts (`ec2-user-data.sh` and `deploy.sh`) natively support **AWS Systems Manager Parameter Store Standard Tier**, which is **100% free indefinitely**.

### ⚠️ Pitfall 4: Orphaned EBS Volumes and Snapshots
- **The Risk:** Terminating an EC2 instance without deleting its associated EBS volume leaves the disk accumulating unattached storage fees.
- **Sentinel Mitigation:** CloudFormation template marks `DeleteOnTermination: true` on all instance block device mappings.

---

## 4. Setting Up Zero-Spend CloudWatch Billing Alarms

Before provisioning any AWS infrastructure, establish an AWS Budget and CloudWatch Billing Alarm:

```bash
# 1. Create an SNS Topic for Billing Notifications
aws sns create-topic --name cloudops-sentinel-billing-alerts

# 2. Subscribe your email address
aws sns subscribe \
    --topic-arn arn:aws:sns:us-east-1:YOUR_ACCOUNT_ID:cloudops-sentinel-billing-alerts \
    --protocol email \
    --notification-endpoint your-email@example.com

# 3. Create CloudWatch Metric Alarm for estimated charges > $1.00 USD
aws cloudwatch put-metric-alarm \
    --region us-east-1 \
    --alarm-name "Sentinel-ZeroDollar-BudgetAlert" \
    --alarm-description "Alerts immediately if monthly AWS charges exceed $1.00" \
    --metric-name EstimatedCharges \
    --namespace AWS/Billing \
    --statistic Maximum \
    --period 21600 \
    --threshold 1.00 \
    --comparison-operator GreaterThanThreshold \
    --evaluation-periods 1 \
    --alarm-actions arn:aws:sns:us-east-1:YOUR_ACCOUNT_ID:cloudops-sentinel-billing-alerts
```

