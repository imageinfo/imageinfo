use std::cmp::Ordering;

const TOKEN_BYTES: usize = 128;
const EXPONENT_MAGNITUDE: i16 = 308;
// A bounded mantissa multiplied by a u128 denominator has at most 167 digits.
const PRODUCT_DIGITS: usize = TOKEN_BYTES + 39;

/// An exact finite decimal literal or exact signed rational observation.
#[derive(Clone, Debug)]
pub struct ExactNumber {
    negative: bool,
    // Most significant first, with leading and trailing zeroes omitted.
    digits: Vec<u8>,
    power: i16,
    denominator: u128,
}

impl ExactNumber {
    /// Construct an exact rational. A zero denominator is unavailable.
    pub fn from_rational(numerator: i128, denominator: u128) -> Option<Self> {
        if denominator == 0 {
            return None;
        }
        let digits = numerator.unsigned_abs().to_string();
        Some(Self::from_digits(
            numerator < 0,
            digits.bytes(),
            0,
            denominator,
        ))
    }

    /// Parse one JSON number using the v1 spelling and resource bounds.
    pub fn from_json_number(token: &str) -> Option<Self> {
        let bytes = token.as_bytes();
        if bytes.len() > TOKEN_BYTES {
            return None;
        }
        let (negative, unsigned) = match bytes.strip_prefix(b"-") {
            Some(unsigned) => (true, unsigned),
            None => (false, bytes),
        };
        let exponent_start = unsigned.iter().position(|byte| matches!(byte, b'e' | b'E'));
        let (mantissa, exponent) = match exponent_start {
            Some(index) => (&unsigned[..index], parse_exponent(&unsigned[index + 1..])?),
            None => (unsigned, 0),
        };
        let decimal_start = mantissa.iter().position(|byte| *byte == b'.');
        let (integer, fraction) = match decimal_start {
            Some(index) => {
                let fraction = &mantissa[index + 1..];
                if fraction.is_empty() || !fraction.iter().all(u8::is_ascii_digit) {
                    return None;
                }
                (&mantissa[..index], fraction)
            }
            None => (mantissa, &[][..]),
        };
        if integer.is_empty()
            || (integer[0] == b'0' && integer.len() > 1)
            || !integer.iter().all(u8::is_ascii_digit)
        {
            return None;
        }

        Some(Self::from_digits(
            negative,
            integer.iter().chain(fraction).copied(),
            exponent - fraction.len() as i16,
            1,
        ))
    }

    fn from_digits(
        negative: bool,
        digits: impl Iterator<Item = u8>,
        mut power: i16,
        denominator: u128,
    ) -> Self {
        let mut digits: Vec<_> = digits
            .skip_while(|digit| *digit == b'0')
            .map(|digit| digit - b'0')
            .collect();
        while digits.last() == Some(&0) {
            digits.pop();
            power += 1;
        }
        Self {
            negative: negative && !digits.is_empty(),
            digits,
            power,
            denominator,
        }
    }

    pub(super) fn is_integer_literal(&self) -> bool {
        debug_assert_eq!(self.denominator, 1);
        self.digits.is_empty() || self.power >= 0
    }

    fn magnitude_cmp(&self, other: &Self) -> Ordering {
        if self.digits.is_empty() || other.digits.is_empty() {
            return self.digits.len().cmp(&other.digits.len());
        }
        let left = product(&self.digits, other.denominator);
        let right = product(&other.digits, self.denominator);
        let left_digits = &left[..product_len(&left)];
        let right_digits = &right[..product_len(&right)];
        let left_scale = left_digits.len() as i16 + self.power;
        let right_scale = right_digits.len() as i16 + other.power;
        left_scale.cmp(&right_scale).then_with(|| {
            let width = left_digits.len().max(right_digits.len());
            let extend = |digits: &[u8]| digits.len()..width;
            left_digits
                .iter()
                .rev()
                .copied()
                .chain(extend(left_digits).map(|_| 0))
                .cmp(
                    right_digits
                        .iter()
                        .rev()
                        .copied()
                        .chain(extend(right_digits).map(|_| 0)),
                )
        })
    }
}

impl PartialEq for ExactNumber {
    fn eq(&self, other: &Self) -> bool {
        self.cmp(other) == Ordering::Equal
    }
}

impl Eq for ExactNumber {}

impl PartialOrd for ExactNumber {
    fn partial_cmp(&self, other: &Self) -> Option<Ordering> {
        Some(self.cmp(other))
    }
}

impl Ord for ExactNumber {
    fn cmp(&self, other: &Self) -> Ordering {
        match (self.negative, other.negative) {
            (true, true) => other.magnitude_cmp(self),
            (true, false) => Ordering::Less,
            (false, true) => Ordering::Greater,
            (false, false) => self.magnitude_cmp(other),
        }
    }
}

fn parse_exponent(bytes: &[u8]) -> Option<i16> {
    let (sign, digits) = match bytes {
        [b'-', digits @ ..] => (-1, digits),
        [b'+', digits @ ..] => (1, digits),
        digits => (1, digits),
    };
    if digits.is_empty() {
        return None;
    }
    let mut magnitude = 0;
    for &digit in digits {
        if !digit.is_ascii_digit() {
            return None;
        }
        magnitude = 10 * magnitude + i16::from(digit - b'0');
        if magnitude > EXPONENT_MAGNITUDE {
            return None;
        }
    }
    Some(sign * magnitude)
}

// Cross-multiply decimal digits using bounded scratch storage. Each inner sum
// consists of one digit product, one stored digit, and a carry of at most 9.
fn product(digits: &[u8], mut factor: u128) -> [u8; PRODUCT_DIGITS] {
    let mut result = [0; PRODUCT_DIGITS];
    let mut offset = 0;
    while factor != 0 {
        let multiplier = (factor % 10) as u8;
        let mut carry = 0;
        for (index, &digit) in digits.iter().rev().enumerate() {
            let slot = &mut result[offset + index];
            let sum = digit * multiplier + *slot + carry;
            *slot = sum % 10;
            carry = sum / 10;
        }
        result[offset + digits.len()] = carry;
        factor /= 10;
        offset += 1;
    }
    result
}

fn product_len(product: &[u8; PRODUCT_DIGITS]) -> usize {
    product
        .iter()
        .rposition(|digit| *digit != 0)
        .map_or(0, |index| index + 1)
}
