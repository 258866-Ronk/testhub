pipeline {
  agent any
  stages {
    stage('Trigger') {
      steps { script {
        def r = sh(script: "curl -s -X POST http://testhub:9090/api/v1/runs \
          -H 'Authorization: Bearer $TOKEN' -H 'Content-Type: application/json' \
          -d '{"suiteId":1}'", returnStdout: true).trim()
        env.RUN_NO = readJSON(text: r).data.run_no
      }}
    }
    stage('Wait & Gate') {
      steps { script {
        timeout(time: 5, unit: 'MINUTES') {
          waitUntil {
            def g = sh(script: "curl -s http://testhub:9090/api/v1/runs/${RUN_NO}/gate \
              -H 'Authorization: Bearer $TOKEN'", returnStdout: true)
            return readJSON(text: g).data.allowed == true
          }
        }
      }}
    }
  }
}
