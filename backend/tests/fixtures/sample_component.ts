export function exportedFunction(inputValue: string): string {
  return inputValue.trim();
}

export class ExportedService {
  process(inputValue: string): string {
    return inputValue.toUpperCase();
  }
}

interface LocalShape {
  fieldName: string;
}

export const arrowHandler = (inputValue: string): string => {
  return inputValue.toLowerCase();
};

const functionExpressionHandler = function (inputValue: string): string {
  return inputValue;
};
