//! Password requirements for newly encrypted database destinations.
//! Existing database unlock credentials are deliberately not validated here.

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum NewDatabasePasswordError {
    TooShort,
    MissingUppercase,
    MissingDigit,
    MissingSpecialCharacter,
}

pub fn validate_new_database_password(password: &str) -> Result<(), NewDatabasePasswordError> {
    if password.chars().count() < 8 {
        return Err(NewDatabasePasswordError::TooShort);
    }
    if !password.chars().any(char::is_uppercase) {
        return Err(NewDatabasePasswordError::MissingUppercase);
    }
    if !password.chars().any(|c| c.is_ascii_digit()) {
        return Err(NewDatabasePasswordError::MissingDigit);
    }
    if !password
        .chars()
        .any(|c| !c.is_alphanumeric() && !c.is_whitespace())
    {
        return Err(NewDatabasePasswordError::MissingSpecialCharacter);
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn accepts_compliant_password() {
        assert_eq!(validate_new_database_password("Minglefield9!"), Ok(()));
    }

    #[test]
    fn rejects_each_missing_requirement() {
        assert_eq!(
            validate_new_database_password("A1!sho"),
            Err(NewDatabasePasswordError::TooShort)
        );
        assert_eq!(
            validate_new_database_password("lowercase9!"),
            Err(NewDatabasePasswordError::MissingUppercase)
        );
        assert_eq!(
            validate_new_database_password("Uppercase!"),
            Err(NewDatabasePasswordError::MissingDigit)
        );
        assert_eq!(
            validate_new_database_password("Uppercase9"),
            Err(NewDatabasePasswordError::MissingSpecialCharacter)
        );
    }

    #[test]
    fn whitespace_is_not_a_special_character() {
        assert_eq!(
            validate_new_database_password("Uppercase9 "),
            Err(NewDatabasePasswordError::MissingSpecialCharacter)
        );
    }
}
