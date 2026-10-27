/*
 * Public survey submit logic (vanilla JavaScript, no libraries).
 *
 * Sends the form to api/survey.php with fetch(), shows any validation
 * errors next to the matching question, and swaps the form for the
 * "thank you" panel on success.
 */
document.addEventListener('DOMContentLoaded', function () {
    const form = document.getElementById('surveyForm');
    if (!form) return;

    const generalError = document.getElementById('surveyGeneralError');
    const status = document.getElementById('surveyStatus');
    const submitButton = document.getElementById('surveySubmit');
    const thankYou = document.getElementById('surveyThankYou');

    function clearErrors() {
        generalError.hidden = true;
        generalError.textContent = '';

        form.querySelectorAll('.survey-error').forEach(function (el) {
            el.hidden = true;
            el.textContent = '';
        });

        form.querySelectorAll('.survey-question.has-error').forEach(function (el) {
            el.classList.remove('has-error');
        });
    }

    function showErrors(errors) {
        let firstField = null;

        Object.keys(errors).forEach(function (key) {
            const message = errors[key];

            const field = form.querySelector('.survey-question[data-question="' + key + '"]');
            const errorText = form.querySelector('.survey-error[data-error-for="' + key + '"]');

            if (field) {
                field.classList.add('has-error');
                if (!firstField) firstField = field;
            }

            if (errorText) {
                errorText.textContent = message;
                errorText.hidden = false;
            }
        });

        if (firstField) {
            firstField.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }
    }

    // Show/hide the free-text box for "Other" checkboxes.
    form.querySelectorAll('[data-other-toggle]').forEach(function (checkbox) {
        const key = checkbox.getAttribute('data-other-toggle');
        const textInput = form.querySelector('[data-other-input="' + key + '"]');

        if (!textInput) return;

        checkbox.addEventListener('change', function () {
            if (checkbox.checked) {
                textInput.hidden = false;
                textInput.focus();
            } else {
                textInput.hidden = true;
                textInput.value = '';
            }
        });
    });

    form.addEventListener('submit', function (event) {
        event.preventDefault();

        clearErrors();
        status.textContent = 'Sending...';
        submitButton.disabled = true;

        fetch('/api/survey.php', {
            method: 'POST',
            body: new FormData(form),
            headers: { 'X-Requested-With': 'XMLHttpRequest' }
        })
            .then(function (response) {
                return response.json().catch(function () {
                    return { success: false, message: 'Unexpected server response.' };
                });
            })
            .then(function (data) {
                if (data.success) {
                    form.hidden = true;
                    thankYou.hidden = false;
                    thankYou.scrollIntoView({ behavior: 'smooth', block: 'center' });
                    return;
                }

                status.textContent = '';

                if (data.errors) {
                    generalError.textContent = data.message || 'Please check the highlighted questions.';
                    generalError.hidden = false;
                    showErrors(data.errors);
                } else {
                    generalError.textContent = data.message || 'Sorry, something went wrong. Please try again.';
                    generalError.hidden = false;
                    generalError.scrollIntoView({ behavior: 'smooth', block: 'center' });
                }
            })
            .catch(function () {
                generalError.textContent = 'Network error. Please check your connection and try again.';
                generalError.hidden = false;
            })
            .finally(function () {
                if (!form.hidden) {
                    submitButton.disabled = false;
                }
                status.textContent = '';
            });
    });
});
