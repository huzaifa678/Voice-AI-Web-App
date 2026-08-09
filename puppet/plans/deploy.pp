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
) {
  $mk = '/snap/bin/microk8s'
  $helm = '/snap/bin/helm'
  $groq = $groq_api_key.unwrap
  $google_pass = $google_app_password.unwrap
  $kubeconfig = "/home/${node_user}/.kube/config"
  $image_set = $image_tag ? { '' => '', default => "--set image.tag=${image_tag}" }

  if $refresh_repo {
    run_command("git -C ${repo_dir} pull --ff-only", $targets)
  }

  run_command("${mk} kubectl create namespace ${namespace} --dry-run=client -o yaml | ${mk} kubectl apply -f -",
    $targets)
  run_command(
    "${mk} kubectl -n ${namespace} create secret generic ${secret_name} --from-literal=GROQ_API_KEY='${groq}' --dry-run=client -o yaml | ${mk} kubectl apply -f -",
    $targets)
  run_command(
    "${mk} kubectl -n ${namespace} create secret generic ${google_secret_name} --from-literal=GOOGLE_USER_EMAIL='${google_user_email}' --from-literal=GOOGLE_APP_PASSWORD='${google_pass}' --dry-run=client -o yaml | ${mk} kubectl apply -f -",
    $targets)

  # the two Helm commands
  run_command("cd ${repo_dir}/voice-ai-chart && ${helm} dependency build", $targets)
  run_command(
    "cd ${repo_dir}/voice-ai-chart && ${helm} --kubeconfig ${kubeconfig} upgrade --install ${release} ./ --namespace ${namespace} --create-namespace --set groq.existingSecret=${secret_name} --set google.existingSecret=${google_secret_name} ${image_set}",
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
