use super::{CompileError, ExpressionError, Issue, IssueKind, Scalar, request};
use std::{
    cmp::Ordering,
    collections::{BTreeMap, BTreeSet},
};

const EXPRESSION_BYTES: usize = 4_096;
const TOKEN_LIMIT: usize = 1_024;
const NESTING_LIMIT: usize = 32;
const PREDICATE_LIMIT: usize = 128;
const KEYWORDS: [&str; 11] = [
    "exists", "absent", "value", "alias", "param", "false", "true", "null", "not", "and", "or",
];

#[derive(Debug)]
pub(super) enum Node {
    Predicate(Predicate),
    Not(usize, Box<Node>),
    And(usize, Box<Node>, Box<Node>),
    Or(usize, Box<Node>, Box<Node>),
}

impl Node {
    pub(super) fn offset(&self) -> usize {
        match self {
            Self::Predicate(predicate) => predicate.offset,
            Self::Not(offset, _) | Self::And(offset, ..) | Self::Or(offset, ..) => *offset,
        }
    }
}

#[derive(Debug)]
pub(super) struct Predicate {
    offset: usize,
    pub(super) selector: String,
    pub(super) kind: PredicateKind,
}

impl Predicate {
    pub(super) fn issue(&self, kind: IssueKind) -> Issue {
        Issue {
            selector: Some(self.selector.clone()),
            expression_offset: Some(self.offset),
            kind,
        }
    }
}

#[derive(Debug)]
pub(super) enum PredicateKind {
    Exists,
    Absent,
    Value {
        view: View,
        comparison: Comparison,
        literal: Scalar,
    },
}

#[derive(Debug)]
pub(super) enum View {
    Raw,
    Normalized,
}

#[derive(Clone, Copy, Debug)]
pub(super) enum Comparison {
    Eq,
    Ne,
    Lt,
    Le,
    Gt,
    Ge,
}

impl Comparison {
    pub(super) fn is_equality(self) -> bool {
        matches!(self, Self::Eq | Self::Ne)
    }

    pub(super) fn test(self, ordering: Ordering) -> bool {
        match self {
            Self::Eq => ordering.is_eq(),
            Self::Ne => ordering.is_ne(),
            Self::Lt => ordering.is_lt(),
            Self::Le => ordering.is_le(),
            Self::Gt => ordering.is_gt(),
            Self::Ge => ordering.is_ge(),
        }
    }
}

pub(super) fn parse(
    expression: &str,
    selectors: &BTreeSet<String>,
    aliases: &BTreeMap<String, String>,
    parameters: &BTreeMap<String, Scalar>,
) -> Result<Node, CompileError> {
    if expression.is_empty() || expression.len() > EXPRESSION_BYTES {
        return Err(error(0, ExpressionError::Bytes));
    }
    let mut parser = Parser {
        tokens: tokenize(expression)?.into_iter().peekable(),
        end: expression.len(),
        predicates: 0,
        selectors,
        aliases,
        parameters,
    };
    let node = parser.or(0)?;
    if let Some(token) = parser.tokens.next() {
        return Err(error(token.offset, ExpressionError::Syntax));
    }
    Ok(node)
}

#[derive(Clone, Copy)]
struct Token<'a> {
    text: &'a str,
    offset: usize,
}

fn tokenize(expression: &str) -> Result<Vec<Token<'_>>, CompileError> {
    let bytes = expression.as_bytes();
    let mut tokens = Vec::new();
    let mut end = 0;
    while end < bytes.len() {
        let offset = end;
        let first = bytes[end];
        end += 1;
        match first {
            b' ' | b'\t' | b'\r' | b'\n' => continue,
            b'"' => {
                end =
                    string_end(bytes, end).ok_or_else(|| error(offset, ExpressionError::String))?
            }
            b'(' | b')' | b',' => {}
            b'=' | b'!' | b'<' | b'>' => {
                if bytes.get(end) == Some(&b'=') {
                    end += 1;
                }
            }
            b'a'..=b'z' | b'A'..=b'Z' => {
                let keyword = KEYWORDS
                    .into_iter()
                    .find(|word| expression[offset..].starts_with(word))
                    .ok_or_else(|| error(offset, ExpressionError::Syntax))?;
                end = offset + keyword.len();
            }
            b'0'..=b'9' | b'-' => {
                while bytes
                    .get(end)
                    .is_some_and(|byte| byte.is_ascii_digit() || b".eE+-".contains(byte))
                {
                    end += 1;
                }
            }
            _ => return Err(error(offset, ExpressionError::Syntax)),
        }
        if tokens.len() == TOKEN_LIMIT {
            return Err(error(offset, ExpressionError::Tokens));
        }
        tokens.push(Token {
            text: &expression[offset..end],
            offset,
        });
    }
    Ok(tokens)
}

fn string_end(bytes: &[u8], mut index: usize) -> Option<usize> {
    while let Some(byte) = bytes.get(index) {
        index += 1;
        match byte {
            b'"' => return Some(index),
            b'\\' => index += 1,
            _ => {}
        }
    }
    None
}

struct Parser<'expression, 'bindings> {
    tokens: std::iter::Peekable<std::vec::IntoIter<Token<'expression>>>,
    end: usize,
    predicates: usize,
    selectors: &'bindings BTreeSet<String>,
    aliases: &'bindings BTreeMap<String, String>,
    parameters: &'bindings BTreeMap<String, Scalar>,
}

impl<'expression> Parser<'expression, '_> {
    fn or(&mut self, nesting: usize) -> Result<Node, CompileError> {
        let mut left = self.and(nesting)?;
        while let Some(operator) = self.take("or") {
            let right = self.and(nesting)?;
            left = Node::Or(operator.offset, Box::new(left), Box::new(right));
        }
        Ok(left)
    }

    fn and(&mut self, nesting: usize) -> Result<Node, CompileError> {
        let mut left = self.unary(nesting)?;
        while let Some(operator) = self.take("and") {
            let right = self.unary(nesting)?;
            left = Node::And(operator.offset, Box::new(left), Box::new(right));
        }
        Ok(left)
    }

    fn unary(&mut self, nesting: usize) -> Result<Node, CompileError> {
        if let Some(token) = self.take("not") {
            check_nesting(nesting, token.offset)?;
            Ok(Node::Not(token.offset, Box::new(self.unary(nesting + 1)?)))
        } else if let Some(token) = self.take("(") {
            check_nesting(nesting, token.offset)?;
            let node = self.or(nesting + 1)?;
            self.expect(")")?;
            Ok(node)
        } else {
            self.predicate()
        }
    }

    fn predicate(&mut self) -> Result<Node, CompileError> {
        let token = self.next()?;
        if !matches!(token.text, "exists" | "absent" | "value") {
            return Err(error(token.offset, ExpressionError::Syntax));
        }
        self.predicates += 1;
        if self.predicates > PREDICATE_LIMIT {
            return Err(error(token.offset, ExpressionError::Predicates));
        }
        self.expect("(")?;
        let selector = self.selector()?;
        let kind = if token.text == "value" {
            self.expect(",")?;
            let view = self.next()?;
            let view = match view.text {
                r#""raw""# => View::Raw,
                r#""normalized""# => View::Normalized,
                _ => return Err(error(view.offset, ExpressionError::Syntax)),
            };
            self.expect(")")?;
            let comparison = self.comparison()?;
            let literal = self.literal()?;
            PredicateKind::Value {
                view,
                comparison,
                literal,
            }
        } else {
            self.expect(")")?;
            if token.text == "exists" {
                PredicateKind::Exists
            } else {
                PredicateKind::Absent
            }
        };
        Ok(Node::Predicate(Predicate {
            offset: token.offset,
            selector,
            kind,
        }))
    }

    fn selector(&mut self) -> Result<String, CompileError> {
        if self.take("alias").is_some() {
            let (token, name) = self.named_operand()?;
            self.aliases
                .get(&name)
                .cloned()
                .ok_or_else(|| error(token.offset, ExpressionError::UnknownAlias))
        } else {
            let token = self.next()?;
            let selector =
                request::string_value(token.text).map_err(|kind| error(token.offset, kind))?;
            if !self.selectors.contains(&selector) {
                return Err(error(token.offset, ExpressionError::UnknownSelector));
            }
            Ok(selector)
        }
    }

    fn literal(&mut self) -> Result<Scalar, CompileError> {
        if self.take("param").is_some() {
            let (token, name) = self.named_operand()?;
            self.parameters
                .get(&name)
                .cloned()
                .ok_or_else(|| error(token.offset, ExpressionError::UnknownParameter))
        } else {
            let token = self.next()?;
            request::scalar(token.text).map_err(|kind| error(token.offset, kind))
        }
    }

    fn named_operand(&mut self) -> Result<(Token<'expression>, String), CompileError> {
        self.expect("(")?;
        let token = self.next()?;
        let value = request::string_value(token.text).map_err(|kind| error(token.offset, kind))?;
        self.expect(")")?;
        Ok((token, value))
    }

    fn comparison(&mut self) -> Result<Comparison, CompileError> {
        let token = self.next()?;
        match token.text {
            "==" => Ok(Comparison::Eq),
            "!=" => Ok(Comparison::Ne),
            "<" => Ok(Comparison::Lt),
            "<=" => Ok(Comparison::Le),
            ">" => Ok(Comparison::Gt),
            ">=" => Ok(Comparison::Ge),
            _ => Err(error(token.offset, ExpressionError::Syntax)),
        }
    }

    fn take(&mut self, text: &str) -> Option<Token<'expression>> {
        self.tokens.next_if(|token| token.text == text)
    }

    fn expect(&mut self, text: &str) -> Result<(), CompileError> {
        let token = self.next()?;
        if token.text != text {
            return Err(error(token.offset, ExpressionError::Syntax));
        }
        Ok(())
    }

    fn next(&mut self) -> Result<Token<'expression>, CompileError> {
        self.tokens
            .next()
            .ok_or_else(|| error(self.end, ExpressionError::Syntax))
    }
}

fn check_nesting(nesting: usize, offset: usize) -> Result<(), CompileError> {
    if nesting == NESTING_LIMIT {
        return Err(error(offset, ExpressionError::Nesting));
    }
    Ok(())
}

fn error(offset: usize, kind: ExpressionError) -> CompileError {
    CompileError::Expression { offset, kind }
}
