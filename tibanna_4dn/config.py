def create_higlass_config(file_format, extra, file_type, data_type):
    return {'file_format': file_format,
            'extra': extra,
            'file_type': file_type,
            'data_type': data_type}

higlass_config = [
    create_higlass_config('mcool', None, 'cooler', 'matrix'),
    create_higlass_config('bw', None, 'bigwig', 'vector'),
    create_higlass_config('bigbed', None, 'cooler', 'matrix'),
    create_higlass_config('beddb', None, 'beddb', 'bedlike'),
    create_higlass_config('bg', 'bw', 'bigwig', 'vector'),
    create_higlass_config('bed', 'beddb', 'beddb', 'bedlike'),
    create_higlass_config('bed', 'bed.multires.mv5', 'multivec', 'multivec')
]
