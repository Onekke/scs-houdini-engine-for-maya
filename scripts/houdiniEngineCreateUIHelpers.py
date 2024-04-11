def find_all_versions(string_array, substring):
    return ','.join([s for s in string_array.split(',') if substring in s])