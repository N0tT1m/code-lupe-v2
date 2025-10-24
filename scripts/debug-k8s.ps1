Write-Host "Debug Kubernetes Issues" -ForegroundColor Red
Write-Host "======================" -ForegroundColor Red

Write-Host ""
Write-Host "Pod Status:" -ForegroundColor Yellow
kubectl get pods -n codelupe -o wide

Write-Host ""
Write-Host "Events (recent):" -ForegroundColor Yellow
kubectl get events -n codelupe --sort-by='.lastTimestamp' | Select-Object -Last 10

Write-Host ""
Write-Host "Processor Logs:" -ForegroundColor Yellow
kubectl logs deployment/processor -n codelupe --tail=20

Write-Host ""
Write-Host "PostgreSQL Logs:" -ForegroundColor Yellow
kubectl logs deployment/postgres -n codelupe --tail=10

Write-Host ""
Write-Host "Describe Processor Pod:" -ForegroundColor Yellow
kubectl describe pods -l app=processor -n codelupe