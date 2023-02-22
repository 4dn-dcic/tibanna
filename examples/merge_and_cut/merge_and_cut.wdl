import "merge.wdl" as sub

workflow merge_and_cut {
    Array[Array[Array[File]]] smallfiles = []
    scatter(smallfiles_ in smallfiles) {
        call sub.merge {input: smallfiles = smallfiles_}
    }
    call cut {input: files = merge.merged}
    output {
        File merged_and_cut = cut.cut1
    }
}

task cut {
    Array[File] files = []
    command {
        cut -c1 ${sep=" " files} > cut1
    }
    output {
        File cut1 = "cut1"
    }
    runtime {
        docker: "ubuntu:20.04"
    }
}
