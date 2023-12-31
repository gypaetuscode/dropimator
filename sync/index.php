<?php

declare(strict_types=1);

require_once('./vendor/autoload.php');

$dotenv = Dotenv\Dotenv::createImmutable(__DIR__);
$dotenv->load();

require_once('./service.php');

$POSTGRES_HOST = $_ENV['POSTGRES_HOST'];
$POSTGRES_PORT = $_ENV['POSTGRES_PORT'];
$POSTGRES_DATABASE = $_ENV['POSTGRES_DATABASE'];
$POSTGRES_USERNAME = $_ENV['POSTGRES_USERNAME'];
$POSTGRES_PASSWORD = $_ENV['POSTGRES_PASSWORD'];

$host = $POSTGRES_HOST;
$port = $POSTGRES_PORT;
$dbname = $POSTGRES_DATABASE;
$user = $POSTGRES_USERNAME;
$password = $POSTGRES_PASSWORD;

$dsn = "pgsql:host=$host;port=$port;dbname=$dbname;user=$user;password=$password";

$pdo = null;

try {
    $pdo = new PDO(($dsn));
    $pdo->setAttribute(PDO::ATTR_ERRMODE, PDO::ERRMODE_EXCEPTION);
} catch (PDOException $ex) {
    echo 'Connection failed: ' . $ex->getMessage() . "\n";
}

$productsStmt = $pdo->query('SELECT * FROM public.products');
$rows = $productsStmt->fetchAll(PDO::FETCH_ASSOC);

foreach ($rows as $row) {
    try {
        // Upsert manufacturer
        $manufacturerName = $row['manufacturer_name'];

        $manufacturerId = getManufacturerByName($manufacturerName);

        if (!$manufacturerId) {
            $manufacturerId = addManufacturer($manufacturerName);
        }

        // Upsert product
        $sku = $row['sku'];
        $name = $row['name'];
        $qty = intval($row['qty'], 10);
        $flavour = trim($row['flavour']);
        $weight = $row['weight'];
        $retailPrice = floatval($row['retail_price']) * 4.96;
        $description = $row['description'];
        $metaTitle = $row['meta_title'];
        $metaDescription = $row['meta_description'];
        $category = $row['category'];

        if (!$description || !$metaTitle || !$metaDescription || !$category) {
            continue;
        };

        $productId = getProductByReference($sku);

        if ($productId) {
            $combinationId = getCombinationByProductId($productId);

            if ($combinationId) {
                updateQuantityWithCombination($productId, $combinationId, $qty);
                continue;
            }

            updateQuantityWithoutCombination($productId, $qty);
            continue;
        }

        echo '------------------THIS IS THE CATEGORY NAME--------------' . $category . "\n";
        $categoryId = getCategoryByName($category);
        echo '------------------THIS IS THE CATEGORY ID--------------' . $categoryId . "\n";

        $productId = addProduct(
            $sku,
            $manufacturerId,
            $name,
            $retailPrice,
            $description,
            $metaTitle,
            $metaDescription,
            $categoryId
        );

        // Upsert image
        $imgUrl = $row['img_url'];

        $imageDeclination = getImageByProductId($productId);

        if (!$imageDeclination) {
            addImageToProduct($imgUrl, $productId);
        }

        if (empty($flavour)) {
            updateQuantityWithoutCombination($productId, $qty);
            continue;
        }

        $productFlavourOptionId = getProductOptionByName('Aroma');
        $productWeightOptionId = getProductOptionByName('Greutate');

        $productFlavourValueOptionId = getProductOptionValueByName($flavour);

        if (!$productFlavourValueOptionId) {
            $productFlavourValueOptionId = addProductOptionValue($productFlavourOptionId, $flavour);
        }

        $productWeightValueOptionId = getProductOptionValueByName($weight);

        if (!$productWeightValueOptionId) {
            $productWeightValueOptionId = addProductOptionValue($productWeightOptionId, $weight);
        }

        $combinationId = addCombination($productId, $productFlavourValueOptionId, $productWeightValueOptionId, $qty, $retailPrice);
        updateQuantityWithCombination($productId, $combinationId, $qty);
    } catch (Exception $ex) {
        continue;
    }
};
