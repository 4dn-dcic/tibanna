workflow md5 {
    call md5_step
}

task md5_step {
    File gz_file
    command {
        run.sh ${gz_file}
    }
    output {
        File report = "report"
    }
    runtime {
        docker: "duplexa/md5:v2"
    }
}
