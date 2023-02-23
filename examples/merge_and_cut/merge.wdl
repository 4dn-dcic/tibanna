workflow merge {
    Array[Array[File]] smallfiles = []
    scatter(smallfiles_ in smallfiles) {
        call paste {input: files = smallfiles_}
    }
    call cat {input: files = paste.pasted}
    output {
        File merged = cat.concatenated
    }
}

task paste {
    Array[File] files = []
    command {
        paste ${sep=" " files} > pasted
    }
    output {
        File pasted = "pasted"
    }
    runtime {
        docker: "ubuntu:20.04"
    }
}

task cat {
    Array[File] files = []
    command {
        cat ${sep=" " files} > concatenated
    }
    output {
        File concatenated = "concatenated"
    }
    runtime {
        docker: "ubuntu:20.04"
    }
}
