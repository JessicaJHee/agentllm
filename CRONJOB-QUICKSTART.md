# Jira Auto-Triage CronJob - Quick Start

Quick guide to deploy the Jira auto-triage workflow as a Kubernetes CronJob on your internal cluster.

## Overview

The Jira triage scripts are included in the main AgentLLM container. Deploy as a Kubernetes CronJob using the existing container image - no need to build or deploy a new image.

## Prerequisites

- [ ] Kubernetes/OpenShift cluster access with `kubectl` or `oc` CLI
- [ ] AgentLLM container available: `codeberg.org/b4mad/agentllm/agentllm:latest`
- [ ] Config file: `rhdh-teams.json` (from JessicaJHee/rhdh-jira-triager-knowledge)
- [ ] Jira API token
- [ ] Gemini API key
- [ ] Slack webhook URL (optional)

## Step 1: Prepare Configuration File

Get your `rhdh-teams.json` configuration file ready:

```bash
# Clone the config repo (if you have access)
git clone https://github.com/JessicaJHee/rhdh-jira-triager-knowledge.git /tmp/jira-config

# Or use your local copy
export CONFIG_FILE="/path/to/rhdh-teams.json"

# Verify it exists and is valid JSON
jq . "$CONFIG_FILE"
```

## Step 2: Encode Credentials to Base64

Kubernetes Secrets require base64-encoded values:

```bash
# Encode Jira API token
echo -n "your-jira-api-token" | base64

# Encode Gemini API key
echo -n "your-gemini-api-key" | base64

# Encode Slack webhook URL (optional)
echo -n "https://hooks.slack.com/services/..." | base64
```

Save these base64 values - you'll need them in Step 3.

## Step 3: Edit CronJob Configuration

Edit `cronjob.yaml` with your values:

```bash
# Open the file
vi cronjob.yaml

# Replace these placeholders in the Secret section:
# - YOUR_BASE64_ENCODED_JIRA_TOKEN
# - YOUR_BASE64_ENCODED_GEMINI_KEY
# - YOUR_BASE64_ENCODED_SLACK_WEBHOOK

# Update the ConfigMap section with your actual rhdh-teams.json content
```

**Important:** Make sure to:
- Use the base64-encoded values from Step 2
- Replace the example team configuration with your actual teams
- Update the namespace if not using `agentllm`

## Step 4: Create ConfigMap from File (Alternative)

Instead of embedding the config in `cronjob.yaml`, you can create the ConfigMap from file:

```bash
# Create ConfigMap from rhdh-teams.json file
kubectl create configmap jira-triager-config \
  --from-file=rhdh-teams.json="$CONFIG_FILE" \
  --namespace=agentllm

# Verify
kubectl get configmap jira-triager-config -n agentllm -o yaml
```

If using this approach, remove the ConfigMap section from `cronjob.yaml` before deploying.

## Step 5: Deploy the CronJob

Apply the CronJob configuration:

```bash
# Create namespace if needed
kubectl create namespace agentllm

# Apply the CronJob, Secret, and ConfigMap
kubectl apply -f cronjob.yaml

# Verify deployment
kubectl get cronjob jira-auto-triage -n agentllm
kubectl get secret jira-triager-secrets -n agentllm
kubectl get configmap jira-triager-config -n agentllm
```

Expected output:
```
NAME               SCHEDULE       SUSPEND   ACTIVE   LAST SCHEDULE   AGE
jira-auto-triage   0 11 * * 1-5   False     0        <none>          10s
```

## Step 6: Test with Manual Job

Test the CronJob before waiting for the schedule:

```bash
# Create a one-off Job from the CronJob
kubectl create job --from=cronjob/jira-auto-triage jira-triage-test -n agentllm

# Watch the job
kubectl get jobs -n agentllm -w

# View logs
kubectl logs -n agentllm job/jira-triage-test --tail=100 -f

# Check status
kubectl describe job jira-triage-test -n agentllm
```

Expected output in logs:
```
=== Jira Auto-Triage Workflow ===
Mode: APPLY
Config: /config/rhdh-teams.json

Running auto-triage...
Using JIRA_API_TOKEN from environment
Creating Jira Triager for user jira-triager-bot
...
✅ Triage completed successfully
```

## Step 7: Enable Dry-Run Mode (Optional)

For initial testing, run in dry-run mode:

```bash
# Edit the CronJob
kubectl edit cronjob jira-auto-triage -n agentllm

# Change this env var:
- name: DRY_RUN
  value: "true"  # Changed from "false"

# Save and exit

# Test again
kubectl create job --from=cronjob/jira-auto-triage jira-triage-dryrun -n agentllm
kubectl logs -n agentllm job/jira-triage-dryrun --tail=100 -f
```

## Quick Commands Reference

### View CronJob Status

```bash
# List CronJobs
kubectl get cronjobs -n agentllm

# Describe CronJob
kubectl describe cronjob jira-auto-triage -n agentllm

# View schedule
kubectl get cronjob jira-auto-triage -n agentllm -o jsonpath='{.spec.schedule}'
```

### View Job History

```bash
# List all jobs created by the CronJob
kubectl get jobs -n agentllm -l app=jira-triager

# View recent jobs with status
kubectl get jobs -n agentllm -l app=jira-triager --sort-by=.metadata.creationTimestamp

# Get logs from most recent job
LATEST_JOB=$(kubectl get jobs -n agentllm -l app=jira-triager --sort-by=.metadata.creationTimestamp -o jsonpath='{.items[-1].metadata.name}')
kubectl logs -n agentllm job/$LATEST_JOB --tail=100
```

### Suspend/Resume CronJob

```bash
# Suspend (stop scheduled runs)
kubectl patch cronjob jira-auto-triage -n agentllm -p '{"spec":{"suspend":true}}'

# Resume
kubectl patch cronjob jira-auto-triage -n agentllm -p '{"spec":{"suspend":false}}'

# Check suspension status
kubectl get cronjob jira-auto-triage -n agentllm -o jsonpath='{.spec.suspend}'
```

### Update Configuration

```bash
# Update ConfigMap from file
kubectl create configmap jira-triager-config \
  --from-file=rhdh-teams.json="$CONFIG_FILE" \
  --namespace=agentllm \
  --dry-run=client -o yaml | kubectl apply -f -

# Update Secret
kubectl create secret generic jira-triager-secrets \
  --from-literal=jira-api-token="new-token" \
  --from-literal=gemini-api-key="new-key" \
  --namespace=agentllm \
  --dry-run=client -o yaml | kubectl apply -f -
```

### Update CronJob Schedule

```bash
# Edit schedule interactively
kubectl edit cronjob jira-auto-triage -n agentllm

# Or patch directly
kubectl patch cronjob jira-auto-triage -n agentllm -p '{"spec":{"schedule":"0 9 * * 1-5"}}'
```

### Delete Resources

```bash
# Delete CronJob only (keeps Secrets and ConfigMaps)
kubectl delete cronjob jira-auto-triage -n agentllm

# Delete all resources
kubectl delete cronjob jira-auto-triage -n agentllm
kubectl delete secret jira-triager-secrets -n agentllm
kubectl delete configmap jira-triager-config -n agentllm
```

## Troubleshooting

### Issue: Job fails with "JIRA_API_TOKEN environment variable is required"

**Solution**: Check Secret is properly created and referenced:
```bash
# Verify Secret exists
kubectl get secret jira-triager-secrets -n agentllm

# Check Secret data (shows keys, not values)
kubectl get secret jira-triager-secrets -n agentllm -o jsonpath='{.data}'

# Verify CronJob references the correct Secret
kubectl get cronjob jira-auto-triage -n agentllm -o yaml | grep -A 10 secretKeyRef
```

### Issue: "Config file not found"

**Solution**: Check ConfigMap is properly mounted:
```bash
# Verify ConfigMap exists
kubectl get configmap jira-triager-config -n agentllm

# Check ConfigMap content
kubectl get configmap jira-triager-config -n agentllm -o yaml

# Verify mount path in CronJob
kubectl get cronjob jira-auto-triage -n agentllm -o yaml | grep -A 5 volumeMounts
```

### Issue: "Image pull failed"

**Solution**: Verify image exists and is accessible:
```bash
# Check image pull status
kubectl describe job <job-name> -n agentllm | grep -A 10 Events

# Pull image manually to test
podman pull codeberg.org/b4mad/agentllm/agentllm:latest

# Update to use specific tag if latest is not available
kubectl patch cronjob jira-auto-triage -n agentllm -p '{"spec":{"jobTemplate":{"spec":{"template":{"spec":{"containers":[{"name":"triage","image":"codeberg.org/b4mad/agentllm/agentllm:v0.1.0-abc123"}]}}}}}}'
```

### Issue: Job runs but doesn't complete

**Solution**: Check logs for errors:
```bash
# Get pod name from job
POD=$(kubectl get pods -n agentllm -l job-name=jira-triage-test -o jsonpath='{.items[0].metadata.name}')

# View logs
kubectl logs -n agentllm $POD --tail=200

# Check pod events
kubectl describe pod -n agentllm $POD
```

### Issue: CronJob doesn't trigger on schedule

**Solution**: Check CronJob configuration:
```bash
# Verify schedule syntax
kubectl get cronjob jira-auto-triage -n agentllm -o jsonpath='{.spec.schedule}'

# Check if suspended
kubectl get cronjob jira-auto-triage -n agentllm -o jsonpath='{.spec.suspend}'

# View last schedule time
kubectl get cronjob jira-auto-triage -n agentllm -o jsonpath='{.status.lastScheduleTime}'
```

## Environment Variables Reference

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `JIRA_API_TOKEN` | ✅ | - | Jira API token (from Secret) |
| `GEMINI_API_KEY` | ✅ | - | Gemini API key (from Secret) |
| `SLACK_WEBHOOK_URL` | ❌ | - | Slack webhook for notifications |
| `JIRA_TRIAGER_CONFIG_FILE` | ✅ | `/config/rhdh-teams.json` | Path to config in container |
| `JIRA_SERVER_URL` | ❌ | `https://issues.redhat.com` | Jira server URL |
| `DRY_RUN` | ❌ | `false` | Preview mode (true/false) |
| `JQL_FILTER` | ❌ | (default filter) | Custom JQL query |
| `LOGURU_LEVEL` | ❌ | `INFO` | Log level (DEBUG/INFO/WARNING/ERROR) |
| `AGNO_DEBUG` | ❌ | `false` | Enable Agno debug logging |

## CronJob Schedule Examples

```yaml
# Weekdays at 6am EST (11am UTC)
schedule: "0 11 * * 1-5"

# Every day at midnight UTC
schedule: "0 0 * * *"

# Every 6 hours
schedule: "0 */6 * * *"

# Every Monday at 9am UTC
schedule: "0 9 * * 1"

# Twice daily: 9am and 5pm UTC
schedule: "0 9,17 * * *"
```

## Security Best Practices

1. **Use namespaced Secrets**: Keep credentials isolated per namespace
2. **RBAC**: Limit who can view/edit Secrets and CronJobs
3. **Read-only ConfigMaps**: Mount ConfigMaps as read-only
4. **Resource limits**: Set memory/CPU limits to prevent resource exhaustion
5. **Image pull policy**: Use `Always` to ensure latest security patches

## For Local Testing

See [LOCAL-TESTING.md](LOCAL-TESTING.md) for local development and testing with Podman before deploying to cluster.

## Additional Resources

- [Kubernetes CronJob Documentation](https://kubernetes.io/docs/concepts/workloads/controllers/cron-jobs/)
- [Managing Secrets](https://kubernetes.io/docs/concepts/configuration/secret/)
- [ConfigMaps](https://kubernetes.io/docs/concepts/configuration/configmap/)
