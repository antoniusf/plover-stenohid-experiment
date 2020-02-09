import random
from plover.system import english_stenotype

class BitReader(object):

    def __init__(self, buffer):

        # we are appending an additional zero byte, since we always load the next byte when the previous one is exhausted.
        # this means that if the last byte is used fully, we'll throw StopIteration even if reading is still allowed.
        # TODO: we maybe need better checking for cases like this. (this is a problem independent of this, since the output is
        # often padded already...)
        self.byte_reader = iter(buffer + bytes([0]))
        self.open_byte = next(self.byte_reader)
        self.bits_left_to_read = 8

    def read_bits(self, num_bits):

        result = 0

        if num_bits >= self.bits_left_to_read:

            mask = (1 << self.bits_left_to_read) - 1
            result = self.open_byte & mask
            num_bits -= self.bits_left_to_read
            self.bits_left_to_read = 8
            self.open_byte = next(self.byte_reader)

            while num_bits >= 8:
                result = (result << 8) | self.open_byte
                num_bits -= 8
                # self.bits_left_to_read remains at 8
                self.open_byte = next(self.byte_reader)

        if num_bits > 0:

            # we always read front (msb) to back (lsb)
            # the first bit we read is self.bits_left_to_read - 1
            # the last bit we read is (self.bits_left_to_read - 1) - num_bits + 1
            # shift the last bit into bit 0
            shifted = self.open_byte >> (self.bits_left_to_read - num_bits)
            mask = (1 << num_bits) - 1
            result = (result << num_bits) | (shifted & mask)
            self.bits_left_to_read -= num_bits

        return result
                

class BitWriter(object):

    def __init__(self):
        self.buffer = bytearray()
        self.open_byte = 0
        self.bits_left_to_fill = 8

    def push_bits(self, number, num_bits):

        assert number < (1 << num_bits)

        # 1 <= self.bits_left_to_fill <= 8

        # first, fill up our current open byte if we can
        if num_bits >= self.bits_left_to_fill:
            new_byte = (self.open_byte << self.bits_left_to_fill) | (number >> (num_bits - self.bits_left_to_fill))
            num_bits -= self.bits_left_to_fill
            number = number & ((1 << num_bits) - 1) # clear out all the bits we don't need anymore

            self.buffer.append(new_byte)
            self.open_byte = 0
            self.bits_left_to_fill = 8

            # self.bits_left_to_fill = 8
            # then, write out all of the whole bytes from the input
            while num_bits >= 8:

                new_byte = number >> (num_bits - 8)
                num_bits -= 8
                number = number & ((1 << num_bits) - 1)
                self.buffer.append(new_byte)

            # num_bits < 8
            # self.bits_left_to_fill = 8
            #  => num_bits < self.bits_left_to_fill

        # else: num_bits < self.bits_left_to_fill
        #  => num_bits < self.bits_left_to_fill in all cases
        # also in all cases: 1 <= self.bits_left_to_fill <= 8

        assert number < (1 << num_bits)

        if num_bits > 0:
            self.open_byte = (self.open_byte << num_bits) | number
            self.bits_left_to_fill -= num_bits
            # self.bits_left_to_fill is still >= 1

        # 1 <= self.bits_left_to_fill <= 8

    def get_output(self):
        """Returns the final buffer, including the currently pending byte, padding it with zeros as necessary."""

        if self.bits_left_to_fill < 8:
            # self.open_byte actually contains data
            # pad with zeros
            final_byte = self.open_byte << self.bits_left_to_fill
            return self.buffer + bytes([final_byte])

        else:
            # copy the buffer to match the semantics of the other branch, where
            # we also end up returning a copy
            return self.buffer[:]
        
def test_bitstreams():

    sequence = []
    total = 0
    for i in range(10000):
        bits = random.randint(1, 64)
        number = random.randint(0, 1 << bits - 1)
        sequence.append((number, bits))
        total += bits

    writer = BitWriter()
    for number, bits in sequence:
        writer.push_bits(number, bits)

    reader = BitReader(writer.get_output())
    for number, bits in sequence:
        result = reader.read_bits(bits)
        #print("expected: {:0{bits}b}".format(number, bits=bits))
        #print("got:      {:0{bits}b}".format(result, bits=bits))
        #print("reader state: {:08b}".format(reader.open_byte))
        #print()
        assert result == number
            

def compress(keylist):

    buffer = BitWriter()

    for string in keylist:

        if string == "no-op":
            # special encoding for no-op
            # since we're using a special encoding for "-",
            # the actual character "-" is free!
            buffer.push_bits(ord("-") | (1 << 8), 9)
            # since we're encoding the whole string at once,
            # we do not need a string-end marker
            
        else:
            for byte in string.encode("utf-8"):
                if byte == ord("-"):
                    buffer.push_bits(0b01, 2)
                else:
                    buffer.push_bits(byte | (1 << 8), 9)

            # push end-of-string
            buffer.push_bits(0b00, 2)

    return buffer.get_output()

def decompress(buffer, num_keys):

    reader = BitReader(buffer)
    keylist = []
    current_string = bytearray()

    while len(keylist) < num_keys:

        is_quoted_byte = reader.read_bits(1)
        if is_quoted_byte:
            byte = reader.read_bits(8)

            if byte == ord("-"):
                # this represents the no-op string as a whole,
                # and can thus not be included in another string.
                # also, this means that it does not need the string 
                # terminator, so we can push it directly
                assert len(current_string) == 0

                keylist.append("no-op")

            else:
                current_string.append(byte)

        else:
            if reader.read_bits(1) == 0:
                # string terminator
                keylist.append(current_string.decode("utf-8"))
                current_string = bytearray()
            else:
                # "-" symbol
                current_string.append(ord("-"))

    return keylist
                
def compress_test_mode(string):

    buffer = BitWriter()

    for byte in string.encode("utf-8"):
        if byte == ord(';'):
            buffer.push_bits(0b00, 2)
        elif byte == ord('-'):
            buffer.push_bits(0b01, 2)
        else:
            buffer.push_bits(byte | (1 << 8), 9)

    # TODO: how to determine length?
    buffer.push_bits(1 << 8, 9)

    # TODO: since we're using a special encoding for "-", the actual (quoted)
    # byte for "-" is free for something else -- maybe a no-op?

    return buffer.get_output()

def decompress_test_mode(buffer):

    reader = BitReader(buffer)
    result = bytearray()

    while True:

        determiner = reader.read_bits(1)
        if determiner == 0:
            if reader.read_bits(1) == 0:
                result.append(ord(";"))
            else:
                result.append(ord("-"))
        else:
            char = reader.read_bits(8)
            if char == 0:
                break
            else:
                result.append(char)

    return result.decode("utf-8")
        

def turn_keymap_into_test_string(keymap):

    actions = []

    for (action, keys) in keymap.items():
        actions.extend([action]*len(keys))

    return ";".join(actions) + ";"

def turn_keymap_into_test_keylist(keymap):

    actions = []

    for (action, keys) in keymap.items():
        actions.extend([action]*len(keys))

    return actions

if __name__ == "__main__":

    print("testing...")
    test_bitstreams()
    print("success!!")

    for (name, keymap) in english_stenotype.KEYMAPS.items():

        string = turn_keymap_into_test_string(keymap)
        keylist = turn_keymap_into_test_keylist(keymap)
        compressed_length = len(compress(keylist))
        assert decompress_test_mode(compress_test_mode(string)) == string
        normal_length = len(string)
        print("{:10}: {:4} bytes ({:4} uncompressed, ratio: {:5.4f})".format(name, compressed_length, normal_length, compressed_length/normal_length))

        # test the actual compression
        assert decompress(compress(keylist), len(keylist)) == keylist
