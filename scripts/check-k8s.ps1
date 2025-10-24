Write-Host "CodeLupe Kubernetes Status" -ForegroundColor Cyan
Write-Host "=========================" -ForegroundColor Cyan

Write-Host ""
Write-Host "Pod Status:" -ForegroundColor Green
kubectl get pods -n codelupe

Write-Host ""
Write-Host "Service Status:" -ForegroundColor Green  
kubectl get services -n codelupe

Write-Host ""
Write-Host "Trainer Logs (last 10 lines):" -ForegroundColor Yellow
kubectl logs --tail=10 deployment/trainer -n codelupe 2>$null

Write-Host ""
Write-Host "Quick Commands:" -ForegroundColor Cyan
Write-Host "* Full trainer logs:  kubectl logs -f deployment/trainer -n codelupe"
Write-Host "* Restart trainer:    kubectl rollout restart deployment/trainer -n codelupe"
Write-Host "* Check events:       kubectl get events -n codelupe --sort-by='.lastTimestamp'"