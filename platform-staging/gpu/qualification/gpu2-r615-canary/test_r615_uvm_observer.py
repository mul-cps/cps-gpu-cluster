import hashlib
import struct
import unittest

import r615_uvm_observer as observer


def elf(data):
    names = b'\0.shstrtab\0__versions\0'
    name_offset = 64 + 3 * 64
    data_offset = name_offset + len(names)
    image = bytearray(data_offset + len(data))
    image[:6] = b'\x7fELF\x02\x01'
    struct.pack_into('<Q', image, 40, 64)
    struct.pack_into('<HHH', image, 58, 64, 3, 1)
    struct.pack_into('<IIQQQQIIQQ', image, 128, 1, 3, 0, 0, name_offset, len(names), 0, 0, 1, 0)
    struct.pack_into('<IIQQQQIIQQ', image, 192, names.index(b'__versions'), 1, 0, 0,
                     data_offset, len(data), 0, 0, 1, 0)
    image[name_offset:data_offset] = names
    image[data_offset:] = data
    return bytes(image)


class RawSectionTest(unittest.TestCase):
    def test_partial_final_byte_is_included_without_readelf_ascii(self):
        data = bytes(range(256)) * 39 + b'\x00' * 33
        self.assertEqual(len(data), 10017)
        image = elf(data)
        receipt = observer.elf_versions(lambda offset, size: image[offset:offset + size])
        self.assertEqual(receipt['sectionBytes'], 10017)
        self.assertEqual(receipt['canonicalHexSHA256'], hashlib.sha256(data.hex().encode()).hexdigest())
        self.assertNotEqual(receipt['canonicalHexSHA256'], hashlib.sha256(data[:-1].hex().encode()).hexdigest())

    def test_truncated_section_is_rejected(self):
        image = elf(b'complete-section\0')[:-1]
        with self.assertRaises(AssertionError):
            observer.elf_versions(lambda offset, size: image[offset:offset + size])

    def test_nonmatching_elf_class_is_rejected(self):
        image = bytearray(elf(b'1234'))
        image[4] = 1
        with self.assertRaises(AssertionError):
            observer.elf_versions(lambda offset, size: image[offset:offset + size])


if __name__ == '__main__':
    unittest.main()
