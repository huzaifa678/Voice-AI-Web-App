# Voice-AI Node Provisioning (Puppet Bolt)

Agentless, SSH driven provisioning of the g4dn GPU node using Puppet Bolt -> Bolt connects over SSH from your machine, applies the `voice_ai::node` manifest for the OS layer and then runs the `voice_ai::provision` plan to bring up MicroK8s, the GPU and the Helm release. The node is managed entirely by you from here, GitHub Actions never touches it.

## Division of Work:

The tooling is layered so each piece owns one concern -> Puppet Bolt owns everything below Kubernetes and Helm owns the app:

* **Puppet Bolt:** provisions the box over SSH -> the apt packages, Docker, the NVIDIA driver, the MicroK8s cluster with its addons and the GPU enablement

* **MicroK8s:** the single node Kubernetes cluster that Bolt installs and enables the `dns`, `hostpath-storage` and `gpu` addons on

* **Helm:** packages and deploys the app + observability stack into the `voice-ai` namespace and stays the source of truth for the release, Bolt just calls the two Helm commands for you

## Project Layout:

* **`bolt-project.yaml`:** the Bolt project definition -> the module name is `voice_ai`

* **`inventory.yaml`:** the target g4dn host and its SSH settings, edit this with your instance DNS/IP and `.pem` key path

* **`hiera.yaml` and `data/common.yaml`:** the package list, the snaps to install and the feature toggles consumed by the node class

* **`manifests/node.pp`:** the `voice_ai::node` class -> apt packages, Docker, the `microk8s` / `helm` / `kubectl` / `k9s` snaps and the NVIDIA T4 driver, every resource guarded so re-runs are a no-op

* **`plans/provision.pp`:** the `voice_ai::provision` plan -> the full node bootstrap that then hands off to the deploy plan for the Helm release

* **`plans/deploy.pp`:** the `voice_ai::deploy` plan -> the Helm only release that never touches the OS, the drivers or reboots the node

## Pre-requisites:

* **Install Bolt on your machine:**

  ```bash
  brew install puppet-bolt
  ```

* **Edit the inventory:** set the instance public DNS/IP and the `.pem` key path inside `inventory.yaml` -> the node is reached as the `ubuntu` user and escalated to `root` via passwordless sudo (`run-as: root`)

## Provisioning the Node:

Run from this `puppet/` directory -> Bolt SSHes in and walks the node through the whole bootstrap:

```bash
bolt plan run voice_ai::provision --targets gpu groq_api_key="$GROQ_API_KEY" google_app_password="$GOOGLE_APP_PASSWORD"
```

The plan runs in order:

1. `apply_prep` installs puppet-agent on the node so `apply()` works

2. applies `voice_ai::node` -> the base packages, Docker, the k8s tooling snaps and the NVIDIA T4 driver, the driver step is skipped when `nvidia-smi` already works (e.g. on the AWS DLAMI)

3. reboots the node once if the driver is not live yet and waits for SSH to come back

4. `microk8s enable dns hostpath-storage gpu` -> the DNS, a storage class for the model PVCs and the GPU operator

5. writes `~/.kube/config` for the deploy user so helm / kubectl / k9s can reach the cluster

6. clones or refreshes the app repo on the node

7. hands off to `voice_ai::deploy` -> creates the `voice-ai-groq` and `voice-ai-google` secrets then runs `helm dependency build` and `helm upgrade --install`, finally patches the GPU operator for time-slicing and prints the advertised GPU slice count (expect `2`)

Provision the node only and skip the Helm release with `deploy=false`:

```bash
bolt plan run voice_ai::provision --targets gpu groq_api_key="$GROQ_API_KEY" google_app_password="$GOOGLE_APP_PASSWORD" deploy=false
```

## Deploying a new Release:

Once the node is provisioned, ship a new image tag without touching the OS -> this is the Helm only path, no drivers and no reboots:

```bash
bolt plan run voice_ai::deploy --targets gpu groq_api_key="$GROQ_API_KEY" google_app_password="$GOOGLE_APP_PASSWORD" image_tag=v1.0.2
```

`groq_api_key` and `google_app_password` are `Sensitive` parameters -> Bolt masks them in the logs and delivers them straight into the in-cluster `voice-ai-groq` and `voice-ai-google` secrets, they are never written to git. The Gmail address defaults to `voiceai3004@gmail.com` and is overridden with `google_user_email=...`.

## Seperation from CI:

Provisioning and deploy live here and are run by you, GitHub Actions only builds -> the two never mix:

* **GitHub Actions (`.github/workflows/ci.yml`):** runs the tests and builds + pushes the Docker image on `v*` tags, it holds no SSH, cluster or GROQ credentials, only `DOCKERHUB_USERNAME` / `DOCKERHUB_TOKEN`

* **Puppet Bolt (this project):** provisions the node and deploys the release, run locally by you so the root SSH stays on your operator machine and never inside a shared runner

So a release is -> tag `v*` -> CI builds and pushes the image -> you run `voice_ai::deploy image_tag=v1.0.2` when you want it live, the deploy is always deliberate and human triggered.

## Notes:

* **Root escalation:** the node is escalated to `root` via passwordless sudo (`run-as: root`), a dedicated non-root deploy user is a reasonable next hardening step

* **k9s snap:** the `k9s` snap uses strict confinement and may not read the kubeconfig, install the k9s binary instead if it fails -> it does not affect the deploy

* **Validate before running:** neither `bolt` nor `puppet` is installed by default, after `brew install puppet-bolt` run `bolt plan show` to load and parse both plans as the real syntax check
