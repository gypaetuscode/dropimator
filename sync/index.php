<?php

declare(strict_types=1);


require_once __DIR__ . '/vendor/autoload.php';

$dotenv = Dotenv\Dotenv::createImmutable(__DIR__);
$dotenv->load();

require_once __DIR__ . '/service.php';

const PRICE_MULTIPLIER = 4.96;

try {
    $pdo = createPdoConnection();
    $products = fetchProducts($pdo);

    foreach ($products as $product) {
        syncProduct($product);
    }
} catch (Throwable $exception) {
    logError('Fatal error while synchronising products', $exception);
    exit(1);
}

function createPdoConnection(): PDO
{
    $dsn = sprintf(
        'pgsql:host=%s;port=%s;dbname=%s;user=%s;password=%s',
        requireEnv('POSTGRES_HOST'),
        requireEnv('POSTGRES_PORT'),
        requireEnv('POSTGRES_DATABASE'),
        requireEnv('POSTGRES_USERNAME'),
        requireEnv('POSTGRES_PASSWORD')
    );

    try {
        $pdo = new PDO($dsn);
        $pdo->setAttribute(PDO::ATTR_ERRMODE, PDO::ERRMODE_EXCEPTION);
        $pdo->setAttribute(PDO::ATTR_DEFAULT_FETCH_MODE, PDO::FETCH_ASSOC);

        return $pdo;
    } catch (PDOException $exception) {
        throw new RuntimeException('Unable to connect to PostgreSQL: ' . $exception->getMessage(), 0, $exception);
    }
}

function fetchProducts(PDO $pdo): array
{
    $statement = $pdo->query('SELECT * FROM public.products');

    if ($statement === false) {
        throw new RuntimeException('Unable to fetch products from PostgreSQL.');
    }

    return $statement->fetchAll();
}

function syncProduct(array $product): void
{
    try {
        $context = buildProductContext($product);

        if ($context === null) {
            return;
        }

        [$metadata, $stock] = $context;

        if ($metadata['existingProductId'] !== null) {
            syncExistingProduct($metadata['existingProductId'], $stock);
            return;
        }

        $productId = createProduct($metadata);
        syncProductImage($productId, $metadata['imageUrl']);
        syncStock($productId, $stock, $metadata['price']);
    } catch (Throwable $exception) {
        logError('Failed to sync product with SKU ' . ($product['sku'] ?? 'unknown'), $exception);
    }
}

/**
 * @return array{0: array<string, mixed>, 1: array<string, mixed>}|null
 */
function buildProductContext(array $product): ?array
{
    $sku = trim((string) ($product['sku'] ?? ''));

    if ($sku === '') {
        logInfo('Skipping product without SKU.');
        return null;
    }

    $manufacturerName = trim((string) ($product['manufacturer_name'] ?? ''));

    if ($manufacturerName === '') {
        logInfo(sprintf('Skipping product %s because manufacturer is missing.', $sku));
        return null;
    }

    $manufacturerId = ensureManufacturerId($manufacturerName);

    if ($manufacturerId === null) {
        logInfo(sprintf('Skipping product %s because manufacturer "%s" could not be created.', $sku, $manufacturerName));
        return null;
    }

    $existingProductId = getProductByReference($sku);

    $name = trim((string) ($product['name'] ?? ''));
    $description = trim((string) ($product['description'] ?? ''));
    $metaTitle = trim((string) ($product['meta_title'] ?? ''));
    $metaDescription = trim((string) ($product['meta_description'] ?? ''));
    $categoryName = trim((string) ($product['category'] ?? ''));

    if ($name === '' || $description === '' || $metaTitle === '' || $metaDescription === '' || $categoryName === '') {
        logInfo(sprintf('Skipping product %s because marketing metadata is incomplete.', $sku));
        return null;
    }

    $categoryId = ensureCategoryId($categoryName);

    if ($categoryId === null) {
        logInfo(sprintf('Skipping product %s because category "%s" could not be resolved.', $sku, $categoryName));
        return null;
    }

    $price = normalisePrice($product['retail_price'] ?? null);

    if ($price === null) {
        logInfo(sprintf('Skipping product %s because retail price is invalid.', $sku));
        return null;
    }

    $quantity = normaliseQuantity($product['qty'] ?? null);
    $flavour = trim((string) ($product['flavour'] ?? ''));
    $weight = trim((string) ($product['weight'] ?? ''));

    $stock = [
        'quantity' => $quantity,
        'flavour' => $flavour,
        'weight' => $weight,
    ];

    $metadata = [
        'sku' => $sku,
        'name' => $name,
        'manufacturerId' => $manufacturerId,
        'categoryId' => $categoryId,
        'price' => $price,
        'description' => $description,
        'metaTitle' => $metaTitle,
        'metaDescription' => $metaDescription,
        'imageUrl' => trim((string) ($product['img_url'] ?? '')),
        'existingProductId' => $existingProductId,
    ];

    return [$metadata, $stock];
}

/**
 * @param mixed $price
 */
function normalisePrice($price): ?float
{
    if ($price === null || $price === '') {
        return null;
    }

    if (!is_numeric($price)) {
        return null;
    }

    return (float) $price * PRICE_MULTIPLIER;
}

/**
 * @param mixed $quantity
 */
function normaliseQuantity($quantity): int
{
    if ($quantity === null || $quantity === '') {
        return 0;
    }

    if (is_numeric($quantity)) {
        return max(0, (int) $quantity);
    }

    return 0;
}

function ensureManufacturerId(string $manufacturerName): ?int
{
    $manufacturerId = getManufacturerByName($manufacturerName);

    if ($manufacturerId !== null) {
        return $manufacturerId;
    }

    try {
        return addManufacturer($manufacturerName);
    } catch (Throwable $exception) {
        logError(sprintf('Unable to create manufacturer "%s".', $manufacturerName), $exception);
        return null;
    }
}

function ensureCategoryId(string $categoryName): ?int
{
    try {
        return getCategoryByName($categoryName);
    } catch (Throwable $exception) {
        logError(sprintf('Unable to retrieve category "%s".', $categoryName), $exception);
        return null;
    }
}

/**
 * @param array<string, mixed> $metadata
 */
function createProduct(array $metadata): int
{
    try {
        $productId = addProduct(
            $metadata['sku'],
            $metadata['manufacturerId'],
            $metadata['name'],
            $metadata['price'],
            $metadata['description'],
            $metadata['metaTitle'],
            $metadata['metaDescription'],
            $metadata['categoryId']
        );

        logInfo(sprintf('Created product %s with ID %d.', $metadata['sku'], $productId));

        return $productId;
    } catch (Throwable $exception) {
        throw new RuntimeException('Unable to create product ' . $metadata['sku'], 0, $exception);
    }
}

function syncExistingProduct(int $productId, array $stock): void
{
    $combinationId = getCombinationByProductId($productId);
    updateStockQuantities($productId, $combinationId, $stock['quantity']);
}

function syncProductImage(int $productId, string $imageUrl): void
{
    if ($imageUrl === '') {
        return;
    }

    if (filter_var($imageUrl, FILTER_VALIDATE_URL) === false) {
        logInfo(sprintf('Skipping image for product %d because URL "%s" is invalid.', $productId, $imageUrl));
        return;
    }

    try {
        if (getImageByProductId($productId) === null) {
            addImageToProduct($imageUrl, $productId);
        }
    } catch (Throwable $exception) {
        logError(sprintf('Failed to sync image for product %d.', $productId), $exception);
    }
}

function syncStock(int $productId, array $stock, float $price): void
{
    $quantity = $stock['quantity'];
    $flavour = $stock['flavour'];
    $weight = $stock['weight'];

    if ($flavour === '' || $weight === '') {
        updateStockQuantities($productId, null, $quantity);
        return;
    }

    $flavourValueId = ensureOptionValue('Aroma', $flavour);
    $weightValueId = ensureOptionValue('Greutate', $weight);

    if ($flavourValueId === null || $weightValueId === null) {
        logInfo(sprintf('Skipping combination sync for product %d because attribute values are missing.', $productId));
        updateStockQuantities($productId, null, $quantity);
        return;
    }

    try {
        $combinationId = addCombination($productId, $flavourValueId, $weightValueId, $quantity, $price);
        logInfo(sprintf('Created combination %d for product %d.', $combinationId, $productId));
        updateStockQuantities($productId, $combinationId, $quantity);
    } catch (Throwable $exception) {
        logError(sprintf('Failed to create combination for product %d.', $productId), $exception);
        updateStockQuantities($productId, null, $quantity);
    }
}

function ensureOptionValue(string $optionName, string $valueName): ?int
{
    try {
        $optionId = getProductOptionByName($optionName);

        if ($optionId === null) {
            logInfo(sprintf('Attribute group "%s" was not found.', $optionName));
            return null;
        }

        $valueId = getProductOptionValueByName($valueName);

        if ($valueId !== null) {
            return $valueId;
        }

        return addProductOptionValue($optionId, $valueName);
    } catch (Throwable $exception) {
        logError(sprintf('Unable to ensure option value "%s" for attribute "%s".', $valueName, $optionName), $exception);
        return null;
    }
}

function updateStockQuantities(int $productId, ?int $combinationId, int $quantity): void
{
    $target = $combinationId !== null
        ? sprintf('combination %d', $combinationId)
        : 'base product';

    logInfo(sprintf('Updating stock for product %d (%s) to %d.', $productId, $target, $quantity));

    try {
        if ($combinationId !== null) {
            updateQuantityWithCombination($productId, $combinationId, $quantity);
        } else {
            updateQuantityWithoutCombination($productId, $quantity);
        }
    } catch (Throwable $exception) {
        logError(sprintf('Failed to update stock for product %d.', $productId), $exception);
    }
}

function requireEnv(string $key): string
{
    if (!isset($_ENV[$key]) || $_ENV[$key] === '') {
        throw new RuntimeException(sprintf('Environment variable "%s" is missing.', $key));
    }

    return $_ENV[$key];
}

function logInfo(string $message): void
{
    echo sprintf('[%s] %s%s', date('c'), $message, PHP_EOL);
}

function logError(string $message, ?Throwable $exception = null): void
{
    $fullMessage = $message;

    if ($exception !== null) {
        $fullMessage .= sprintf(' - %s', $exception->getMessage());
    }

    echo sprintf('[%s] ERROR: %s%s', date('c'), $fullMessage, PHP_EOL);
}
