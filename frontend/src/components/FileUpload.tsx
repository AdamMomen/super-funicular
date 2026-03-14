import { useRef, useState } from "react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Upload, X, FileJson } from "lucide-react";
import { cn } from "@/lib/utils";

interface FileUploadProps {
  onFileSelect: (file: File) => void;
  onConfigSelect?: (file: File) => void;
  onClear?: () => void;
  onConfigClear?: () => void;
  selectedFile?: File | null;
  configFile?: File | null;
  accept?: string;
  label?: string;
  className?: string;
}

export function FileUpload({
  onFileSelect,
  onConfigSelect,
  onClear,
  onConfigClear,
  selectedFile,
  configFile,
  accept = ".csv",
  label = "Upload CSV",
  className,
}: FileUploadProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const configRef = useRef<HTMLInputElement>(null);
  const [isDragging, setIsDragging] = useState(false);

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    const f = e.dataTransfer.files?.[0];
    if (f && (accept === ".csv" ? f.name.endsWith(".csv") : true)) {
      onFileSelect(f);
    }
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = () => setIsDragging(false);

  return (
    <div className={cn("space-y-3", className)}>
      <Card
        className={cn(
          "border-dashed border cursor-pointer transition-colors p-6 border-border",
          isDragging && "border-primary/50 bg-secondary",
          !isDragging && "hover:border-muted-foreground/30 hover:bg-secondary/30"
        )}
        onClick={() => inputRef.current?.click()}
        onDrop={handleDrop}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
      >
        <input
          ref={inputRef}
          type="file"
          accept={accept}
          className="hidden"
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) onFileSelect(f);
            e.target.value = "";
          }}
        />
        {selectedFile ? (
          <div className="flex items-center justify-between gap-2">
            <span className="text-sm font-medium truncate">{selectedFile.name}</span>
            <span className="text-xs text-muted-foreground shrink-0">
              {(selectedFile.size / 1024).toFixed(1)} KB
            </span>
            {onClear && (
              <Button
                type="button"
                variant="ghost"
                size="icon"
                className="h-7 w-7 shrink-0"
                onClick={(e) => {
                  e.stopPropagation();
                  onClear();
                }}
              >
                <X className="h-3.5 w-3.5" />
              </Button>
            )}
          </div>
        ) : (
          <div className="flex flex-col items-center gap-2 text-muted-foreground">
            <Upload className="h-8 w-8" />
            <span className="text-sm">{label}</span>
            <span className="text-xs">or drag and drop</span>
          </div>
        )}
      </Card>
      {onConfigSelect && (
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => configRef.current?.click()}
          >
            <input
              ref={configRef}
              type="file"
              accept=".json"
              className="hidden"
              onChange={(e) => {
                const f = e.target.files?.[0];
                if (f) onConfigSelect(f);
                e.target.value = "";
              }}
            />
            <FileJson className="h-3.5 w-3.5 mr-1.5" />
            {configFile ? configFile.name : "Config (JSON)"}
          </Button>
          {configFile && onConfigClear && (
            <Button
              variant="ghost"
              size="icon"
              className="h-8 w-8"
              onClick={onConfigClear}
            >
              <X className="h-3.5 w-3.5" />
            </Button>
          )}
        </div>
      )}
    </div>
  );
}
