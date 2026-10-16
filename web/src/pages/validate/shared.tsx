import { DEFAULT_VALIDATE_FORM, type ValidateForm } from '@/state/forms'
import { usePageState } from '@/state/store'

export function useValidateForm() {
  return usePageState<ValidateForm>('validate:form', DEFAULT_VALIDATE_FORM)
}
