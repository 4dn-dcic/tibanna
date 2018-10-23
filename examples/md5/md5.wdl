workflow md5 {
    call md5_step
}

task md5_step {
    File gzfile
    command {
        run.sh ${gzfile}
    }
    output {
        File report = "report"
    }
    runtime {
        docker: "duplexa/md5:v2"
    }
}
