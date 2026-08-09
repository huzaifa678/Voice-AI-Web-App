plan voice_ai::provision (
  TargetSpec        $targets             = 'gpu',
  Sensitive[String] $groq_api_key,
  Sensitive[String] $google_app_password,
  String            $google_user_email   = 'voiceai3004@gmail.com',
  String            $node_user           = 'ubuntu',
  String            $repo_url            = 'https://github.com/huzaifa678/Voice-AI-Web-App.git',
  String            $repo_dir            = '/home/ubuntu/Voice-AI-Web-App',
  String            $namespace           = 'voice-ai',
  String            $release             = 'voice-ai',
  String            $secret_name         = 'voice-ai-groq',
  String            $google_secret_name  = 'voice-ai-google',
  Boolean           $deploy              = true,
) {
  $mk = '/snap/bin/microk8s'

  apply_prep($targets)

  apply($targets) {
    include voice_ai::node
  }

  $nvidia = run_command('nvidia-smi > /dev/null 2>&1 && echo ok || echo reboot',
    $targets, '_catch_errors' => true)
  if $nvidia.first.value['stdout'] =~ /reboot/ {
    out::message('NVIDIA driver not live yet - rebooting node')
    run_command('reboot', $targets, '_catch_errors' => true)
    wait_until_available($targets, 'wait_time' => 600, 'retry_interval' => 10)
  }

  run_command("${mk} status --wait-ready", $targets)
  run_command("${mk} enable dns hostpath-storage", $targets)
  run_command("${mk} enable gpu", $targets)

  run_command(
    "install -d -o ${node_user} -g ${node_user} -m 700 /home/${node_user}/.kube && ${mk} config > /home/${node_user}/.kube/config && chown ${node_user}:${node_user} /home/${node_user}/.kube/config && chmod 600 /home/${node_user}/.kube/config",
    $targets)

  run_command("test -d ${repo_dir}/.git && git -C ${repo_dir} pull --ff-only || git clone ${repo_url} ${repo_dir}",
    $targets)

  if $deploy {
    return run_plan('voice_ai::deploy', {
      'targets'             => $targets,
      'groq_api_key'        => $groq_api_key,
      'google_app_password' => $google_app_password,
      'google_user_email'   => $google_user_email,
      'node_user'           => $node_user,
      'repo_dir'            => $repo_dir,
      'namespace'           => $namespace,
      'release'             => $release,
      'secret_name'         => $secret_name,
      'google_secret_name'  => $google_secret_name,
      'refresh_repo'        => false,
    })
  }

  return run_command("${mk} kubectl get node -o jsonpath='{.items[0].status.capacity.nvidia\\.com/gpu}'",
    $targets, '_catch_errors' => true)
}
