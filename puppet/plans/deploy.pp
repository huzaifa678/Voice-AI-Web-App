plan voice_ai::deploy (
  TargetSpec        $targets             = 'gpu',
  Sensitive[String] $groq_api_key,
  Sensitive[String] $google_app_password,
  String            $google_user_email   = 'voiceai3004@gmail.com',
  String            $node_user           = 'ubuntu',
  String            $repo_dir            = '/home/ubuntu/Voice-AI-Web-App',
  String            $namespace           = 'voice-ai',
  String            $release             = 'voice-ai',
  String            $secret_name         = 'voice-ai-groq',
  String            $google_secret_name  = 'voice-ai-google',
  String            $image_tag           = '',
  Boolean           $refresh_repo        = true,
  Boolean           $observability       = true,
) {
  $mk = '/snap/bin/microk8s'
  $helm = '/snap/bin/helm'
  $groq = $groq_api_key.unwrap
  $google_pass = $google_app_password.unwrap
  $kubeconfig = "/home/${node_user}/.kube/config"
  $image_set = $image_tag ? { '' => '', default => "--set image.tag=${image_tag}" }

  # The heavy observability subcharts (loki/tempo/thanos/prometheus/otel) are
  # memory-hungry for one node and need full S3 wiring; keep them off by default
  # so a single-node deploy fits and doesn't hit the loki storage config. Enable
  # with observability=true once those values are properly configured.
  $obs_set = $observability ? {
    true    => '',
    default => '--set loki.enabled=false --set tempo.enabled=false --set thanos.enabled=false --set kube-prometheus-stack.enabled=false --set opentelemetry-collector.enabled=false',
  }

  if $refresh_repo {
    run_command("git -C ${repo_dir} pull --ff-only", $targets)
  }

  run_command("${mk} kubectl create namespace ${namespace} --dry-run=client -o yaml | ${mk} kubectl apply -f -",
    $targets)

  run_command(
    "${mk} kubectl -n ${namespace} create secret generic ${secret_name} --from-literal=GROQ_API_KEY=\"\$GROQ_API_KEY\" --dry-run=client -o yaml | ${mk} kubectl apply -f -",
    $targets,
    'env_vars' => { 'GROQ_API_KEY' => $groq })
  run_command(
    "${mk} kubectl -n ${namespace} create secret generic ${google_secret_name} --from-literal=GOOGLE_USER_EMAIL='${google_user_email}' --from-literal=GOOGLE_APP_PASSWORD=\"\$GOOGLE_APP_PASSWORD\" --dry-run=client -o yaml | ${mk} kubectl apply -f -",
    $targets,
    'env_vars' => { 'GOOGLE_APP_PASSWORD' => $google_pass })

  run_command(
    "printf 'type: S3\\nconfig:\\n  bucket: voice-ai-thanos\\n  endpoint: s3.us-east-1.amazonaws.com\\n  region: us-east-1\\n' | ${mk} kubectl -n ${namespace} create secret generic thanos-objstore --from-file=objstore.yml=/dev/stdin --dry-run=client -o yaml | ${mk} kubectl apply -f -",
    $targets)

  run_command(
    "${helm} repo add --force-update bitnami https://charts.bitnami.com/bitnami && ${helm} repo add --force-update icoretech https://icoretech.github.io/helm && ${helm} repo add --force-update grafana https://grafana.github.io/helm-charts && ${helm} repo add --force-update prometheus-community https://prometheus-community.github.io/helm-charts && ${helm} repo add --force-update open-telemetry https://open-telemetry.github.io/opentelemetry-helm-charts && ${helm} repo add --force-update ingress-nginx https://kubernetes.github.io/ingress-nginx && ${helm} repo update",
    $targets)

  # the two Helm commands
  run_command("cd ${repo_dir}/voice-ai-chart && ${helm} dependency build", $targets)
  run_command(
    "cd ${repo_dir}/voice-ai-chart && ${helm} --kubeconfig ${kubeconfig} upgrade --install ${release} ./ --namespace ${namespace} --create-namespace --set groq.existingSecret=${secret_name} --set google.existingSecret=${google_secret_name} ${obs_set} ${image_set}",
    $targets)

  # keep GPU time-slicing active (ConfigMap ships with the chart)
  run_command(
    "for i in \$(seq 1 60); do ${mk} kubectl get clusterpolicy cluster-policy -n gpu-operator-resources >/dev/null 2>&1 && break; sleep 10; done",
    $targets, '_catch_errors' => true)
  run_command(
    "${mk} kubectl patch clusterpolicy cluster-policy -n gpu-operator-resources --type merge -p '{\"spec\":{\"devicePlugin\":{\"config\":{\"name\":\"time-slicing-config\",\"default\":\"any\"}}}}'",
    $targets, '_catch_errors' => true)

  return run_command("${mk} kubectl get node -o jsonpath='{.items[0].status.capacity.nvidia\\.com/gpu}'",
    $targets, '_catch_errors' => true)
}
