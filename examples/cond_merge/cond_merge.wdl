# The output of this workflow would be
# cond_merge.paste.pasted if the number of input files < 2.
# cond_merge.cat.concatenated if the number of input files >= 2.
workflow cond_merge {
    Array[File] smallfiles = []
    if(length(smallfiles)>2) {
        call paste {input: files = smallfiles}
    }
    if(length(smallfiles)<=2) {
        call cat {input: files = smallfiles}
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
        docker: "ubuntu:16.04"
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
        docker: "ubuntu:16.04"
    }
}
